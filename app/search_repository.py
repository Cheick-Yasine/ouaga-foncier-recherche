"""Lecture en seule lecture des annonces candidates dans Neon."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row

from app.config import Settings, get_settings
from app.database import DatabaseNotConfiguredError
from app.neighborhoods import resolve_neighborhood
from app.normalization import normalize_property_type
from app.search_engine import SearchCandidate
from app.text_features import (
    extract_document_status,
    extract_proximity,
    extract_viability,
)


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _candidate_from_row(
    row: dict[str, Any],
    *,
    now: datetime,
) -> SearchCandidate:
    text = (
        _optional_text(row.get("texte_nettoye"))
        or _optional_text(row.get("resume_court"))
        or ""
    )
    neighborhood = resolve_neighborhood(
        text,
        _optional_text(row.get("quartier_zone")),
    )
    collected_at = row.get("premiere_collecte")
    if collected_at is not None and collected_at.tzinfo is None:
        collected_at = collected_at.replace(tzinfo=timezone.utc)
    age_days = (
        max(0.0, (now - collected_at).total_seconds() / 86_400)
        if collected_at is not None
        else None
    )
    proximity = extract_proximity(text)
    viability = extract_viability(text)
    document = extract_document_status(
        _optional_text(row.get("statut_document")),
        text,
    )

    return SearchCandidate(
        identifier=str(row["id"]),
        text=text,
        property_type=normalize_property_type(
            _optional_text(row.get("type_bien_normalise"))
            or _optional_text(row.get("type_bien")),
            text,
        ),
        neighborhood=neighborhood.canonical if neighborhood.in_scope else None,
        price_fcfa=_optional_float(row.get("prix_fcfa")),
        area_m2=_optional_float(row.get("superficie_m2")),
        proximity=None if proximity == "non_precisee" else proximity,
        viability=None if viability == "non_precisee" else viability,
        document_status=None if document == "non_precise" else document,
        age_days=age_days,
        url=_optional_text(row.get("url")),
        publication_label=_optional_text(row.get("date_publication")),
        collected_at=collected_at.isoformat() if collected_at else None,
        contact=_optional_text(row.get("contacts_whatsapp")),
    )


def load_recent_candidates(
    max_age_days: int | None = None,
    settings: Settings | None = None,
    *,
    now: datetime | None = None,
    pool_limit: int = 5_000,
) -> list[SearchCandidate]:
    """Charge les annonces admissibles sans modifier Neon."""

    current_settings = settings or get_settings()
    if current_settings.database_url is None:
        raise DatabaseNotConfiguredError(
            "DATABASE_URL n'est pas configurée dans l'environnement."
        )

    current_time = now or datetime.now(timezone.utc)
    with psycopg.connect(
        current_settings.database_url.get_secret_value(),
        connect_timeout=10,
        row_factory=dict_row,
    ) as connection:
        with connection.transaction():
            connection.execute("SET TRANSACTION READ ONLY")
            age_clause = (
                "premiere_collecte >= CURRENT_TIMESTAMP - "
                "(%s * INTERVAL '1 day') AND "
                if max_age_days is not None
                else ""
            )
            parameters: tuple[int, ...] = (
                (max_age_days, pool_limit)
                if max_age_days is not None
                else (pool_limit,)
            )
            rows = connection.execute(
                f"""
                SELECT
                    id::text AS id,
                    url,
                    date_publication,
                    type_bien,
                    type_bien_normalise,
                    quartier_zone,
                    superficie_m2,
                    prix_fcfa,
                    statut_document,
                    contacts_whatsapp,
                    resume_court,
                    texte_nettoye,
                    premiere_collecte
                FROM public.annonces
                WHERE {age_clause}
                      NOT (prix_fcfa IS NULL AND superficie_m2 IS NULL)
                  AND COALESCE(
                      NULLIF(LOWER(TRIM(type_bien_normalise)), ''),
                      NULLIF(LOWER(TRIM(type_bien)), ''),
                      ''
                  ) <> 'villa'
                ORDER BY premiere_collecte DESC NULLS LAST, id
                LIMIT %s
                """,
                parameters,
            ).fetchall()

    return [
        _candidate_from_row(dict(row), now=current_time)
        for row in rows
    ]


def load_candidate_by_id(
    identifier: str,
    settings: Settings | None = None,
    *,
    now: datetime | None = None,
) -> SearchCandidate | None:
    """Charge une annonce admissible par identifiant, sans aucune écriture."""

    current_settings = settings or get_settings()
    if current_settings.database_url is None:
        raise DatabaseNotConfiguredError(
            "DATABASE_URL n'est pas configurée dans l'environnement."
        )

    current_time = now or datetime.now(timezone.utc)
    with psycopg.connect(
        current_settings.database_url.get_secret_value(),
        connect_timeout=10,
        row_factory=dict_row,
    ) as connection:
        with connection.transaction():
            connection.execute("SET TRANSACTION READ ONLY")
            row = connection.execute(
                """
                SELECT
                    id::text AS id,
                    url,
                    date_publication,
                    type_bien,
                    type_bien_normalise,
                    quartier_zone,
                    superficie_m2,
                    prix_fcfa,
                    statut_document,
                    contacts_whatsapp,
                    resume_court,
                    texte_nettoye,
                    premiere_collecte
                FROM public.annonces
                WHERE id::text = %s
                  AND NOT (prix_fcfa IS NULL AND superficie_m2 IS NULL)
                  AND COALESCE(
                      NULLIF(LOWER(TRIM(type_bien_normalise)), ''),
                      NULLIF(LOWER(TRIM(type_bien)), ''),
                      ''
                  ) <> 'villa'
                LIMIT 1
                """,
                (identifier,),
            ).fetchone()

    if row is None:
        return None
    return _candidate_from_row(dict(row), now=current_time)
