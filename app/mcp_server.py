"""Serveur MCP en lecture seule pour le moteur Ouaga Foncier."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import psycopg
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from app.config import get_settings
from app.database import DatabaseNotConfiguredError
from app.public_references import public_announcement_id
from app.search_engine import (
    parse_search_description,
    price_per_square_metre,
    rank_candidates,
)
from app.search_repository import load_recent_candidates
from app.semantic_filter import apply_semantic_filter, sanitize_external_text

mcp = FastMCP(
    "Ouaga Foncier Recherche",
    instructions=(
        "Utilise ces outils pour chercher des terrains, parcelles et maisons "
        "à Ouagadougou. Les outils sont en lecture seule et ne retournent jamais "
        "les contacts des annonceurs."
    ),
    stateless_http=True,
    json_response=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[
            "ouaga-foncier-mcp.onrender.com",
            "localhost:*",
            "127.0.0.1:*",
        ],
        allowed_origins=[
            "https://chatgpt.com",
            "https://chat.openai.com",
            "http://localhost:*",
            "http://127.0.0.1:*",
        ],
    ),
)


def _criteria_payload(criteria) -> dict[str, Any]:
    return {
        "description": criteria.description,
        "type_bien": criteria.property_type,
        "quartier": criteria.neighborhood,
        "prix_fcfa": criteria.price_fcfa,
        "prix_est_un_maximum": criteria.price_is_maximum,
        "superficie_m2": criteria.area_m2,
        "proximite": criteria.proximity,
        "viabilite": criteria.viability,
        "document": criteria.document_status,
        "contraintes_obligatoires": sorted(criteria.required_fields),
        "anciennete_maximale_jours": criteria.max_age_days,
    }


def _public_result(result) -> dict[str, Any]:
    candidate = result.candidate
    return {
        "id": public_announcement_id(candidate.identifier),
        "title": " à ".join(
            value
            for value in (candidate.property_type, candidate.neighborhood)
            if value
        )
        or "Annonce immobilière",
        "url": f"{get_settings().public_app_url}/?annonce={public_announcement_id(candidate.identifier)}",
        "description": sanitize_external_text(candidate.text),
        "date_publication": candidate.publication_label,
        "type_bien": candidate.property_type,
        "quartier": candidate.neighborhood,
        "prix_fcfa": candidate.price_fcfa,
        "prix_m2_fcfa": price_per_square_metre(candidate),
        "superficie_m2": candidate.area_m2,
        "document": candidate.document_status,
        "score": result.score,
        "couverture": result.coverage,
        "explications": [
            explanation
            for explanation in result.explanations
            if explanation.casefold() != "même type de bien".casefold()
        ],
    }


def interpreter_recherche(description: str) -> dict[str, Any]:
    """Extrait les critères immobiliers d'une description en français."""

    if len(description.strip()) < 3:
        return {"erreur": "La description doit contenir au moins 3 caractères."}
    return _criteria_payload(parse_search_description(description))


def rechercher_annonces(
    description: str,
    limit: int = 10,
    criteres_obligatoires: list[str] | None = None,
    anciennete_jours: int = 30,
    utiliser_filtre_llm: bool = True,
) -> dict[str, Any]:
    """Recherche et filtre les annonces correspondant à une description."""

    if len(description.strip()) < 3:
        return {"erreur": "La description doit contenir au moins 3 caractères."}
    if anciennete_jours not in {7, 30, 90}:
        return {"erreur": "La période doit être de 7, 30 ou 90 jours."}

    allowed = {
        "quartier",
        "prix",
        "superficie",
        "type_bien",
        "statut_document",
        "proximite",
        "viabilite",
    }
    required = set(criteres_obligatoires or [])
    unknown = sorted(required - allowed)
    if unknown:
        return {"erreur": "Critères obligatoires inconnus : " + ", ".join(unknown)}

    safe_limit = min(max(int(limit), 1), 20)
    settings = get_settings()
    criteria = replace(
        parse_search_description(description),
        required_fields=frozenset(required),
        max_age_days=anciennete_jours,
    )

    try:
        candidates = load_recent_candidates(anciennete_jours)
    except (DatabaseNotConfiguredError, psycopg.Error):
        return {"erreur": "La base d'annonces est temporairement indisponible."}

    local_limit = (
        max(safe_limit, settings.llm_candidate_limit)
        if utiliser_filtre_llm
        else safe_limit
    )
    ranked = rank_candidates(criteria, candidates, limit=local_limit)
    if utiliser_filtre_llm:
        semantic = apply_semantic_filter(criteria, ranked, settings=settings)
        selected = semantic.results[:safe_limit]
        semantic_used = semantic.used
        semantic_model = semantic.model
        semantic_fallback = semantic.fallback
    else:
        selected = ranked[:safe_limit]
        semantic_used = False
        semantic_model = None
        semantic_fallback = False

    return {
        "criteres": _criteria_payload(criteria),
        "candidats_evalues": len(candidates),
        "nombre_resultats": len(selected),
        "filtre_semantique_utilise": semantic_used,
        "modele_semantique": semantic_model,
        "repli_classement_local": semantic_fallback,
        "results": [_public_result(result) for result in selected],
    }


def search(query: str) -> dict[str, Any]:
    """Recherche MCP compatible : retourne les annonces pertinentes."""

    return rechercher_annonces(query, limit=10)


def fetch(id: str) -> dict[str, Any]:
    """Retourne le détail public associé à une référence MCP opaque."""

    try:
        candidates = load_recent_candidates(None)
    except (DatabaseNotConfiguredError, psycopg.Error):
        return {"erreur": "La base d'annonces est temporairement indisponible."}

    candidate = next(
        (
            item
            for item in candidates
            if public_announcement_id(item.identifier) == id
        ),
        None,
    )
    if candidate is None:
        return {"erreur": "Annonce introuvable."}

    return {
        "id": public_announcement_id(candidate.identifier),
        "title": " à ".join(
            value
            for value in (candidate.property_type, candidate.neighborhood)
            if value
        )
        or "Annonce immobilière",
        "text": sanitize_external_text(candidate.text),
        "url": None,
        "metadata": {
            "date_publication": candidate.publication_label,
            "type_bien": candidate.property_type,
            "quartier": candidate.neighborhood,
            "prix_fcfa": candidate.price_fcfa,
            "prix_m2_fcfa": price_per_square_metre(candidate),
            "superficie_m2": candidate.area_m2,
            "document": candidate.document_status,
        },
    }

mcp.tool()(interpreter_recherche)
mcp.tool()(rechercher_annonces)
mcp.tool()(search)
mcp.tool()(fetch)

http_app = mcp.streamable_http_app()


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
