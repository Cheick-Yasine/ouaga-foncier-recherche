"""Serveur MCP en lecture seule pour le moteur Ouaga Foncier."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import psycopg
from mcp.server.fastmcp import FastMCP

from app.config import get_settings
from app.database import DatabaseNotConfiguredError
from app.search_engine import parse_search_description, rank_candidates
from app.search_repository import load_candidate_by_id, load_recent_candidates
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
    }


def _public_result(result) -> dict[str, Any]:
    candidate = result.candidate
    return {
        "id": candidate.identifier,
        "title": " à ".join(
            value
            for value in (candidate.property_type, candidate.neighborhood)
            if value
        )
        or "Annonce immobilière",
        "url": candidate.url,
        "description": sanitize_external_text(candidate.text),
        "date_publication": candidate.publication_label,
        "type_bien": candidate.property_type,
        "quartier": candidate.neighborhood,
        "prix_fcfa": candidate.price_fcfa,
        "superficie_m2": candidate.area_m2,
        "document": candidate.document_status,
        "score": result.score,
        "couverture": result.coverage,
        "explications": list(result.explanations),
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
) -> dict[str, Any]:
    """Recherche et filtre les annonces correspondant à une description."""

    if len(description.strip()) < 3:
        return {"erreur": "La description doit contenir au moins 3 caractères."}

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
        max_age_days=None,
    )

    try:
        candidates = load_recent_candidates(None)
    except (DatabaseNotConfiguredError, psycopg.Error):
        return {"erreur": "La base d'annonces est temporairement indisponible."}

    local_limit = max(safe_limit, settings.llm_candidate_limit)
    ranked = rank_candidates(criteria, candidates, limit=local_limit)
    semantic = apply_semantic_filter(criteria, ranked, settings=settings)
    selected = semantic.results[:safe_limit]

    return {
        "criteres": _criteria_payload(criteria),
        "candidats_evalues": len(candidates),
        "nombre_resultats": len(selected),
        "filtre_semantique_utilise": semantic.used,
        "modele_semantique": semantic.model,
        "repli_classement_local": semantic.fallback,
        "results": [_public_result(result) for result in selected],
    }


def search(query: str) -> dict[str, Any]:
    """Recherche MCP compatible : retourne les annonces pertinentes."""

    return rechercher_annonces(query, limit=10)


def fetch(id: str) -> dict[str, Any]:
    """Retourne le détail public d'une annonce sans aucun contact."""

    try:
        candidate = load_candidate_by_id(id)
    except (DatabaseNotConfiguredError, psycopg.Error):
        return {"erreur": "La base d'annonces est temporairement indisponible."}

    if candidate is None:
        return {"erreur": "Annonce introuvable."}

    return {
        "id": candidate.identifier,
        "title": " à ".join(
            value
            for value in (candidate.property_type, candidate.neighborhood)
            if value
        )
        or "Annonce immobilière",
        "text": sanitize_external_text(candidate.text),
        "url": candidate.url,
        "metadata": {
            "date_publication": candidate.publication_label,
            "type_bien": candidate.property_type,
            "quartier": candidate.neighborhood,
            "prix_fcfa": candidate.price_fcfa,
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
