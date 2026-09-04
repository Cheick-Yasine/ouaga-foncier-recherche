"""Filtre final OpenAI avec minimisation et anonymisation des données."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, replace
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.search_engine import (
    RankedResult,
    SearchCriteria,
    _descriptive_priority,
)

LOGGER = logging.getLogger(__name__)

_URL_RE = re.compile(r"(?i)\b(?:https?://|www\.)\S+")
_EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_PHONE_RE = re.compile(r"(?<!\d)\+?\d(?:[\s.()/-]*\d){7,}(?!\d)")


class SemanticDecision(BaseModel):
    candidate_key: str
    pertinent: bool
    score_pertinence: int = Field(ge=0, le=100)
    raison: str = Field(min_length=1, max_length=240)


class SemanticDecisionBatch(BaseModel):
    decisions: list[SemanticDecision]


@dataclass(frozen=True)
class SemanticFilterOutcome:
    results: list[RankedResult]
    used: bool
    model: str | None
    fallback: bool


def sanitize_external_text(value: str | None, *, limit: int = 1_500) -> str:
    """Retire URL, e-mail et téléphone avant tout envoi externe."""

    text = value or ""
    text = _URL_RE.sub("[lien retire]", text)
    text = _EMAIL_RE.sub("[email retire]", text)
    text = _PHONE_RE.sub("[contact retire]", text)
    return " ".join(text.split())[:limit]


def build_anonymized_payload(
    criteria: SearchCriteria,
    results: list[RankedResult],
    *,
    candidate_limit: int,
) -> tuple[dict[str, Any], dict[str, RankedResult]]:
    """Construit un lot sans identifiant, lien, contact ni date Facebook."""

    selected = results[:candidate_limit]
    key_map = {f"c{index}": result for index, result in enumerate(selected, start=1)}
    payload = {
        "demande": sanitize_external_text(criteria.description, limit=2_000),
        "criteres": {
            "type_bien": criteria.property_type,
            "quartier": criteria.neighborhood,
            "prix_fcfa": criteria.price_fcfa,
            "prix_est_un_maximum": criteria.price_is_maximum,
            "superficie_m2": criteria.area_m2,
            "proximite": criteria.proximity,
            "viabilite": criteria.viability,
            "document": criteria.document_status,
            "contraintes_obligatoires": sorted(criteria.required_fields),
        },
        "annonces": [
            {
                "candidate_key": key,
                "description": sanitize_external_text(result.candidate.text),
                "type_bien": result.candidate.property_type,
                "quartier": result.candidate.neighborhood,
                "prix_fcfa": result.candidate.price_fcfa,
                "superficie_m2": result.candidate.area_m2,
                "base_prix": result.candidate.pricing_note,
                "proximite": result.candidate.proximity,
                "viabilite": result.candidate.viability,
                "document": result.candidate.document_status,
                "score_local": result.score,
            }
            for key, result in key_map.items()
        ],
    }
    return payload, key_map


def _instructions() -> str:
    return (
        "Tu es l'analyste final d'un moteur immobilier à Ouagadougou. "
        "Ta mission est de choisir et classer au maximum les 10 annonces qui répondent "
        "le mieux à la description complète de l'utilisateur. Analyse simultanément "
        "le type de bien, la localisation, le budget, la superficie, le document, "
        "la proximité et la viabilité lorsqu'ils sont demandés. "
        "Le sens de la phrase de l'utilisateur prime sur une simple ressemblance de mots. "
        "Les critères descriptifs explicitement demandés sont prioritaires dans cet ordre : "
        "quartier ou zone, type de bien, document, proximité et viabilité. Classe d'abord "
        "les annonces qui respectent ces critères; prix et superficie servent ensuite à "
        "départager les annonces du même niveau descriptif. "
        "N'invente aucune information absente et signale clairement les compromis. "
        "Ne confonds jamais un prix total avec un prix par hectare ou par m². "
        "Quand base_prix est renseignée, utilise uniquement le coût et la surface "
        "recalculés du lot réellement achetable. "
        "Un budget annoncé, même sans les mots maximum ou FCFA, est un plafond strict. "
        "Quand l'utilisateur demande un bon deal avec seulement un budget, compare les "
        "annonces sous ce plafond et favorise la plus grande superficie réellement "
        "achetable. À superficie proche, favorise le prix le plus proche du budget. "
        "Quand une superficie est demandée, favorise d'abord les annonces proches de "
        "cette superficie, puis le prix total le plus faible; une surface énorme très "
        "éloignée de la demande n'est pas automatiquement un meilleur deal. "
        "Ensuite, départage avec le document et la complétude des informations. "
        "Écarte les annonces hors sujet et les répétitions d'une même annonce, même si "
        "elles ont des identifiants différents. Deux biens réellement distincts peuvent "
        "toutefois avoir le même quartier, le même prix et la même superficie. "
        "Attribue un score comparable de 0 à 100 et écris une raison courte, concrète, "
        "directement utile au choix. Retourne exactement une décision par candidate_key "
        "évaluée, sans clé inventée ni clé répétée."
    )


def apply_semantic_filter(
    criteria: SearchCriteria,
    results: list[RankedResult],
    *,
    settings: Settings | None = None,
    client: Any | None = None,
) -> SemanticFilterOutcome:
    """Filtre et reclasse les meilleurs résultats; revient au local en cas d'échec."""

    current = settings or get_settings()
    if not results or current.openai_api_key is None:
        return SemanticFilterOutcome(results, False, None, bool(results))

    payload, key_map = build_anonymized_payload(
        criteria,
        results,
        candidate_limit=current.llm_candidate_limit,
    )
    api_client = client or OpenAI(
        api_key=current.openai_api_key.get_secret_value(),
        timeout=20.0,
        max_retries=1,
    )

    try:
        response = api_client.responses.parse(
            model=current.llm_model,
            input=[
                {"role": "system", "content": _instructions()},
                {
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=False),
                },
            ],
            text_format=SemanticDecisionBatch,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise ValueError("Sortie structurée absente")

        filtered: list[RankedResult] = []
        seen: set[str] = set()
        seen_announcements: set[str] = set()
        for decision in parsed.decisions:
            if decision.candidate_key in seen:
                continue
            seen.add(decision.candidate_key)
            local = key_map.get(decision.candidate_key)
            if (
                local is None
                or not decision.pertinent
                or decision.score_pertinence < current.llm_relevance_threshold
            ):
                continue
            signature = sanitize_external_text(local.candidate.text).casefold()
            signature = " ".join(signature.split())
            if signature and signature in seen_announcements:
                continue
            if signature:
                seen_announcements.add(signature)
            combined = round(
                0.45 * local.score + 0.55 * decision.score_pertinence,
                2,
            )
            filtered.append(
                replace(
                    local,
                    score=combined,
                    explanations=local.explanations
                    + (f"Filtre sémantique : {decision.raison}",),
                )
            )

        filtered.sort(
            key=lambda item: (
                _descriptive_priority(criteria, item),
                item.score,
                item.coverage,
            ),
            reverse=True,
        )
        return SemanticFilterOutcome(
            results=filtered[:10],
            used=True,
            model=current.llm_model,
            fallback=False,
        )
    except Exception as error:  # l'erreur distante ne doit jamais bloquer la recherche
        LOGGER.warning(
            "Filtre sémantique indisponible (%s); classement local conservé.",
            type(error).__name__,
        )
        return SemanticFilterOutcome(results, False, None, True)
