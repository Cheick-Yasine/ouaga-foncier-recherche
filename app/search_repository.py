"""Lecture en seule lecture des annonces candidates dans Neon."""

from __future__ import annotations

from datetime import datetime, timezone
import re
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


_PER_HECTARE_RE = re.compile(
    r"(?i)(?:/|par)\s*(?:hectare|ha)\b"
    r"|\bl['’]?(?:hectare|ha)\b"
    r"|\bprix\s+(?:de\s+|du\s+)?(?:l['’])?(?:hectare|ha)\b"
)
_PER_SQUARE_METRE_RE = re.compile(
    r"(?i)(?:/|par)\s*(?:m[²2]|metres?\s+carres?)\b"
)
_MINIMUM_HECTARES_RE = re.compile(
    r"(?i)(?:bloc\s+(?:minimum\s+)?de|lot\s+(?:minimum\s+)?de"
    r"|minimum(?:\s+de)?|a\s+partir\s+de|tranche\s+de)\s*"
    r"(\d+(?:[.,]\d+)?)\s*(?:hectares?|ha)\b"
)


def _effective_price_and_area(
    text: str,
    price_fcfa: float | None,
    area_m2: float | None,
) -> tuple[float | None, float | None, str | None]:
    """Convertit un tarif unitaire en ticket et surface réellement achetables."""

    if price_fcfa is None:
        return price_fcfa, area_m2, None

    if _PER_HECTARE_RE.search(text):
        minimum_match = _MINIMUM_HECTARES_RE.search(text)
        hectares = (
            float(minimum_match.group(1).replace(",", "."))
            if minimum_match
            else 1.0
        )
        purchasable_area = hectares * 10_000
        if area_m2 is not None:
            purchasable_area = min(area_m2, purchasable_area)
        return (
            price_fcfa * hectares,
            purchasable_area,
            (
                f"Prix calculé pour le lot minimum de {hectares:g} hectare(s)"
                if minimum_match
                else "Prix et superficie présentés pour 1 hectare"
            ),
        )

    if _PER_SQUARE_METRE_RE.search(text) and area_m2 is not None:
        return (
            price_fcfa * area_m2,
            area_m2,
            "Prix total calculé à partir du tarif au m²",
        )

    return price_fcfa, area_m2, None


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
    effective_price, effective_area, pricing_note = _effective_price_and_area(
        text,
        _optional_float(row.get("prix_fcfa")),
        _optional_float(row.get("superficie_m2")),
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
        price_fcfa=effective_price,
        area_m2=effective_area,
        proximity=None if proximity == "non_precisee" else proximity,
        viability=None if viability == "non_precisee" else viability,
        document_status=None if document == "non_precise" else document,
        age_days=age_days,
        url=_optional_text(row.get("url")),
        publication_label=_optional_text(row.get("date_publication")),
        collected_at=collected_at.isoformat() if collected_at else None,
        contact=_optional_text(row.get("contacts_whatsapp")),
        pricing_note=pricing_note,
    )


_ALLOWED_PROPERTY_TYPES = frozenset({"terrain", "parcelle", "maison"})


def _is_prepared_candidate(candidate: SearchCandidate) -> bool:
    """Applique les règles validées de la base finale avant le classement."""

    return (
        candidate.neighborhood is not None
        and candidate.property_type in _ALLOWED_PROPERTY_TYPES
        and not (
            candidate.price_fcfa is None
            and candidate.area_m2 is None
        )
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

    candidates = [
        _candidate_from_row(dict(row), now=current_time)
        for row in rows
    ]
    return [
        candidate
        for candidate in candidates
        if _is_prepared_candidate(candidate)
    ]
