"""Calcul quotidien du prix médian au m² par quartier.

Le snapshot est calculé une fois par jour à partir de la table finale public.annonces.
Les trois types autorisés (terrain, parcelle, maison) sont regroupés dans une seule
distribution, conformément à la définition métier de l'indicateur.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
import json
import logging
from pathlib import Path
from statistics import median
from typing import Any
import asyncio

import psycopg
from psycopg.rows import dict_row

from app.config import get_settings
from app.database import DatabaseNotConfiguredError
from app.listing_scope import market_scope_eligible, sale_eligible
from app.neighborhoods import neighborhood_key, suggest_canonical_neighborhood
from app.search_engine import SearchCandidate, price_per_square_metre

logger = logging.getLogger(__name__)
CATALOG_PATH = Path(__file__).resolve().parent / "data" / "quartiers_catalogue_201.json"
ALLOWED_PROPERTY_TYPES = frozenset({"terrain", "parcelle", "maison"})
SNAPSHOT_TABLE = "public.market_neighborhood_daily_prices"


def load_neighborhood_catalog(path: Path = CATALOG_PATH) -> list[dict[str, Any]]:
    """Charge les 201 noms canoniques ; les coordonnées ne sont pas requises."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Le catalogue des quartiers doit être une liste.")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in data:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        name = name.strip()
        key = neighborhood_key(name)
        if key and key not in seen:
            seen.add(key)
            result.append({"name": name, "key": key})
    if len(result) != 201:
        raise ValueError(f"Catalogue incomplet : {len(result)} quartiers au lieu de 201.")
    return result


def _finite_positive(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if number <= 0 or number == float("inf") or number != number:
        return None
    return number


def calculate_neighborhood_medians(
    rows: list[dict[str, Any]],
    catalog: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Calcule une médiane par quartier après exclusions et dédoublonnage."""
    catalog_by_key = {item["key"]: item["name"] for item in catalog}
    values: dict[str, list[float]] = defaultdict(list)
    seen: set[str] = set()

    for row in rows:
        if row.get("is_trashed"):
            continue
        raw_type = (row.get("type_bien_normalise") or row.get("type_bien") or "")
        if str(raw_type).strip().casefold() not in ALLOWED_PROPERTY_TYPES:
            continue

        neighborhood = str(row.get("quartier_zone") or "").strip()
        if not neighborhood:
            continue
        canonical = catalog_by_key.get(neighborhood_key(neighborhood))
        if canonical is None:
            alias = suggest_canonical_neighborhood(neighborhood)
            canonical = catalog_by_key.get(neighborhood_key(alias)) if alias else None
        if canonical is None:
            continue

        text = str(row.get("texte_nettoye") or row.get("resume_court") or "")
        if not sale_eligible(text) or not market_scope_eligible(text, neighborhood):
            continue

        identity = str(row.get("url") or row.get("id") or "").strip()
        if not identity or identity in seen:
            continue

        price = _finite_positive(row.get("prix_fcfa"))
        area = _finite_positive(row.get("superficie_m2"))
        if price is None or area is None:
            continue

        candidate = SearchCandidate(
            identifier=str(row.get("id") or identity),
            text=text,
            property_type=str(raw_type).strip().casefold(),
            neighborhood=canonical,
            price_fcfa=price,
            area_m2=area,
        )
        unit_price = price_per_square_metre(candidate)
        if unit_price is None:
            continue

        seen.add(identity)
        values[canonical].append(unit_price)

    return [
        {
            "neighborhood_key": item["key"],
            "neighborhood_name": item["name"],
            "median_price_m2": round(median(values[item["name"]]), 2) if values[item["name"]] else None,
            "listing_count": len(values[item["name"]]),
        }
        for item in catalog
    ]


def refresh_daily_neighborhood_prices(
    *, now: datetime | None = None,
) -> dict[str, Any]:
    """Écrit atomiquement le snapshot du jour ; un appel répété est idempotent."""
    settings = get_settings()
    if settings.database_url is None:
        raise DatabaseNotConfiguredError("DATABASE_URL n'est pas configurée.")

    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    snapshot_date = current.date()
    catalog = load_neighborhood_catalog()
    database_url = settings.database_url.get_secret_value()

    with psycopg.connect(database_url, row_factory=dict_row, connect_timeout=10) as connection:
        with connection.transaction():
            connection.execute("SELECT pg_advisory_xact_lock(hashtext('hakimo-neighborhood-prices-daily'))")
            existing = connection.execute(
                f"SELECT COUNT(*) AS total FROM {SNAPSHOT_TABLE} WHERE snapshot_date = %s",
                (snapshot_date,),
            ).fetchone()["total"]
            if existing == len(catalog):
                return {"date_calcul": snapshot_date.isoformat(), "quartiers": existing, "deja_calcule": True}

            connection.execute("SET LOCAL statement_timeout = '120s'")
            rows = connection.execute(
                """
                SELECT
                    a.id::text AS id,
                    a.url,
                    a.type_bien,
                    a.type_bien_normalise,
                    a.quartier_zone,
                    a.superficie_m2,
                    a.prix_fcfa,
                    a.texte_nettoye,
                    a.resume_court,
                    COALESCE(f.is_trashed, FALSE) AS is_trashed
                FROM public.annonces AS a
                LEFT JOIN public.admin_announcement_flags AS f
                    ON f.announcement_id = a.id::text
                WHERE COALESCE(f.is_trashed, FALSE) = FALSE
                  AND COALESCE(
                    NULLIF(LOWER(TRIM(a.type_bien_normalise)), ''),
                    NULLIF(LOWER(TRIM(a.type_bien)), '')
                  ) IN ('terrain', 'parcelle', 'maison')
                ORDER BY a.id
                """
            ).fetchall()

            calculated = calculate_neighborhood_medians([dict(row) for row in rows], catalog)
            connection.execute(
                f"DELETE FROM {SNAPSHOT_TABLE} WHERE snapshot_date = %s",
                (snapshot_date,),
            )
            connection.executemany(
                f"""
                INSERT INTO {SNAPSHOT_TABLE} (
                    snapshot_date, neighborhood_key, neighborhood_name,
                    median_price_m2, listing_count, calculated_at
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                [
                    (
                        snapshot_date,
                        item["neighborhood_key"],
                        item["neighborhood_name"],
                        item["median_price_m2"],
                        item["listing_count"],
                        current,
                    )
                    for item in calculated
                ],
            )

    return {
        "date_calcul": snapshot_date.isoformat(),
        "quartiers": len(calculated),
        "annonces_utilisees": sum(item["listing_count"] for item in calculated),
        "deja_calcule": False,
    }


def get_latest_neighborhood_prices() -> dict[str, Any] | None:
    """Lit le dernier snapshot enregistré sans recalculer les annonces."""
    settings = get_settings()
    if settings.database_url is None:
        raise DatabaseNotConfiguredError("DATABASE_URL n'est pas configurée.")

    with psycopg.connect(
        settings.database_url.get_secret_value(),
        row_factory=dict_row,
        connect_timeout=10,
    ) as connection:
        latest = connection.execute(
            f"SELECT MAX(snapshot_date) AS snapshot_date FROM {SNAPSHOT_TABLE}"
        ).fetchone()["snapshot_date"]
        if latest is None:
            return None
        rows = connection.execute(
            f"""
            SELECT neighborhood_key, neighborhood_name, median_price_m2,
                   listing_count, calculated_at
            FROM {SNAPSHOT_TABLE}
            WHERE snapshot_date = %s
            ORDER BY neighborhood_name
            """,
            (latest,),
        ).fetchall()

    return {
        "date_calcul": latest.isoformat(),
        "quartiers": [
            {
                "cle": row["neighborhood_key"],
                "nom": row["neighborhood_name"],
                "prix_m2_median_fcfa": float(row["median_price_m2"]) if row["median_price_m2"] is not None else None,
                "annonces_avec_prix_m2": row["listing_count"],
                "calcule_le": row["calculated_at"].isoformat() if row["calculated_at"] else None,
            }
            for row in rows
        ],
    }


async def neighborhood_price_snapshot_loop() -> None:
    """Au démarrage, complète le snapshot du jour ; puis exécute à 02:00 UTC."""
    while True:
        try:
            await asyncio.to_thread(refresh_daily_neighborhood_prices)
        except Exception:
            logger.exception("Échec du calcul quotidien des prix médians au m² par quartier.")
            await asyncio.sleep(30 * 60)
            continue

        now = datetime.now(timezone.utc)
        next_run = (now + timedelta(days=1)).replace(
            hour=2, minute=0, second=0, microsecond=0
        )
        await asyncio.sleep(max(60, (next_run - now).total_seconds()))
