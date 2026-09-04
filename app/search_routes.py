"""Routes de recherche et interprétation des demandes."""

from __future__ import annotations

from dataclasses import replace
import logging
from time import perf_counter
from typing import Literal

import psycopg
from fastapi import APIRouter, Cookie, HTTPException
from pydantic import BaseModel, Field

from app.auth import SESSION_COOKIE, get_session_user
from app.contacts import mask_contact, whatsapp_url
from app.config import get_settings
from app.database import DatabaseNotConfiguredError
from app.search_engine import (
    RankedResult,
    SearchCriteria,
    parse_search_description,
    rank_candidates,
)
from app.search_repository import load_recent_candidates
from app.semantic_filter import apply_semantic_filter


LOGGER = logging.getLogger(__name__)


RequiredField = Literal[
    "quartier",
    "prix",
    "superficie",
    "type_bien",
    "statut_document",
    "proximite",
    "viabilite",
]


class InterpretRequest(BaseModel):
    description: str = Field(min_length=3, max_length=2_000)
    required_fields: set[RequiredField] = Field(default_factory=set)
    max_age_days: int | None = Field(default=None, ge=1, le=365)


class SearchRequest(InterpretRequest):
    limit: int = Field(default=10, ge=1, le=10)


class InterpretedCriteria(BaseModel):
    description: str
    type_bien: str | None
    quartier: str | None
    prix_fcfa: float | None
    prix_est_un_maximum: bool
    superficie_m2: float | None
    proximite: str | None
    viabilite: str | None
    statut_document: str | None
    contraintes_obligatoires: list[str]
    anciennete_maximale_jours: int | None


class SearchResult(BaseModel):
    id: str
    texte: str
    url: str | None
    date_publication: str | None
    premiere_collecte: str | None
    anciennete_jours: float | None
    type_bien: str | None
    quartier: str | None
    prix_fcfa: float | None
    superficie_m2: float | None
    note_prix: str | None
    statut_document: str | None
    proximite: str | None
    viabilite: str | None
    score: float
    couverture: float
    composantes: dict[str, float | None]
    explications: list[str]
    contact: str | None
    contact_masque: str | None
    lien_whatsapp: str | None
    connexion_requise_pour_contact: bool


class SearchResponse(BaseModel):
    criteres: InterpretedCriteria
    candidats_evalues: int
    nombre_resultats: int
    resultats: list[SearchResult]
    filtre_semantique_utilise: bool
    modele_semantique: str | None
    repli_classement_local: bool


router = APIRouter(prefix="/search", tags=["Recherche"])


def _with_options(payload: InterpretRequest) -> SearchCriteria:
    criteria = parse_search_description(payload.description)
    return replace(
        criteria,
        required_fields=frozenset(payload.required_fields),
        max_age_days=payload.max_age_days,
    )


def _criteria_response(criteria: SearchCriteria) -> InterpretedCriteria:
    return InterpretedCriteria(
        description=criteria.description,
        type_bien=criteria.property_type,
        quartier=criteria.neighborhood,
        prix_fcfa=criteria.price_fcfa,
        prix_est_un_maximum=criteria.price_is_maximum,
        superficie_m2=criteria.area_m2,
        proximite=criteria.proximity,
        viabilite=criteria.viability,
        statut_document=criteria.document_status,
        contraintes_obligatoires=sorted(criteria.required_fields),
        anciennete_maximale_jours=criteria.max_age_days,
    )


def _result_response(
    result: RankedResult,
    *,
    authenticated: bool,
) -> SearchResult:
    candidate = result.candidate
    visible_contact = candidate.contact if authenticated else None
    return SearchResult(
        id=candidate.identifier,
        texte=candidate.text,
        url=candidate.url if authenticated else None,
        date_publication=candidate.publication_label,
        premiere_collecte=candidate.collected_at,
        anciennete_jours=(
            round(candidate.age_days, 2)
            if candidate.age_days is not None
            else None
        ),
        type_bien=candidate.property_type,
        quartier=candidate.neighborhood,
        prix_fcfa=candidate.price_fcfa,
        superficie_m2=candidate.area_m2,
        note_prix=candidate.pricing_note,
        statut_document=candidate.document_status,
        proximite=candidate.proximity,
        viabilite=candidate.viability,
        score=result.score,
        couverture=result.coverage,
        composantes=dict(result.components),
        explications=list(result.explanations),
        contact=visible_contact,
        contact_masque=mask_contact(candidate.contact),
        lien_whatsapp=whatsapp_url(visible_contact),
        connexion_requise_pour_contact=bool(
            candidate.contact and not authenticated
        ),
    )


@router.post("/interpret", response_model=InterpretedCriteria)
def interpret_search(payload: InterpretRequest) -> InterpretedCriteria:
    return _criteria_response(_with_options(payload))


@router.post("", response_model=SearchResponse)
def search(
    payload: SearchRequest,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> SearchResponse:
    """Interprète la demande, lit Neon et retourne au plus dix annonces uniques."""

    total_started = perf_counter()

    criteria_started = perf_counter()
    criteria = _with_options(payload)
    criteria_ms = (perf_counter() - criteria_started) * 1_000
    LOGGER.info(
        "search_stage stage=criteria status=completed elapsed_ms=%.1f",
        criteria_ms,
    )

    neon_started = perf_counter()
    try:
        candidates = load_recent_candidates(criteria.max_age_days)
    except DatabaseNotConfiguredError as error:
        raise HTTPException(status_code=503, detail=str(error)) from None
    except psycopg.Error:
        raise HTTPException(
            status_code=503,
            detail="La lecture des annonces dans Neon a échoué.",
        ) from None
    neon_ms = (perf_counter() - neon_started) * 1_000
    LOGGER.info(
        "search_stage stage=neon status=completed elapsed_ms=%.1f candidates=%d",
        neon_ms,
        len(candidates),
    )

    session_started = perf_counter()
    try:
        authenticated = get_session_user(session_token) is not None
    except (DatabaseNotConfiguredError, psycopg.Error):
        authenticated = False
    session_ms = (perf_counter() - session_started) * 1_000
    LOGGER.info(
        "search_stage stage=session status=completed elapsed_ms=%.1f",
        session_ms,
    )

    settings = get_settings()
    local_started = perf_counter()
    local_limit = max(payload.limit, settings.llm_candidate_limit)
    ranked_local = rank_candidates(criteria, candidates, limit=local_limit)
    local_ms = (perf_counter() - local_started) * 1_000
    LOGGER.info(
        (
            "search_stage stage=local_rank status=completed "
            "elapsed_ms=%.1f results=%d"
        ),
        local_ms,
        len(ranked_local),
    )

    LOGGER.info(
        "search_stage stage=semantic status=started candidates=%d",
        len(ranked_local),
    )
    semantic_started = perf_counter()
    semantic = apply_semantic_filter(
        criteria,
        ranked_local,
        settings=settings,
    )
    semantic_ms = (perf_counter() - semantic_started) * 1_000
    LOGGER.info(
        (
            "search_stage stage=semantic status=completed elapsed_ms=%.1f "
            "llm_used=%s fallback=%s"
        ),
        semantic_ms,
        semantic.used,
        semantic.fallback,
    )

    ranked = semantic.results[: payload.limit]
    total_ms = (perf_counter() - total_started) * 1_000
    LOGGER.info(
        (
            "search_timing total_ms=%.1f criteria_ms=%.1f neon_ms=%.1f "
            "session_ms=%.1f local_rank_ms=%.1f openai_ms=%.1f "
            "candidates=%d local_results=%d final_results=%d "
            "llm_used=%s fallback=%s"
        ),
        total_ms,
        criteria_ms,
        neon_ms,
        session_ms,
        local_ms,
        semantic_ms,
        len(candidates),
        len(ranked_local),
        len(ranked),
        semantic.used,
        semantic.fallback,
    )

    return SearchResponse(
        criteres=_criteria_response(criteria),
        candidats_evalues=len(candidates),
        nombre_resultats=len(ranked),
        resultats=[
            _result_response(result, authenticated=authenticated)
            for result in ranked
        ],
        filtre_semantique_utilise=semantic.used,
        modele_semantique=semantic.model,
        repli_classement_local=semantic.fallback,
    )
