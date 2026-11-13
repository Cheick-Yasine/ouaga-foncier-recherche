"""Calcule une fois par jour le prix médian demandé au m² par quartier.

Le calcul mélange volontairement tous les types de biens présents dans
public.annonces. Il ne conserve que des agrégats quotidiens, sans données
personnelles ni texte d'annonce.
"""
from __future__ import annotations

import json
import logging
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import psycopg
from psycopg.rows import dict_row

from app.config import get_settings
from app.listing_scope import market_scope_eligible, sale_eligible
from app.market_stats import publication_time
from app.neighborhoods import (
    neighborhood_key,
    resolve_neighborhood,
    suggest_canonical_neighborhood,
)
from app.search_engine import SearchCandidate, price_per_square_metre

CATALOG_PATH = ROOT / "app" / "data" / "quartiers_catalogue_201.json"
MIGRATION_PATH = ROOT / "db" / "migrations" / "006_neighborhood_price_daily.sql"
LOG = logging.getLogger("hakimo.neighborhood_prices")


def load_catalogue() -> tuple[list[str], dict[str, str]]:
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    names = [
        item["name"].strip()
        for item in data
        if isinstance(item, dict)
        and isinstance(item.get("name"), str)
        and item["name"].strip()
    ]
    by_key = {neighborhood_key(name): name for name in names}
    if not names:
        raise RuntimeError("Le catalogue des quartiers est vide.")
    return names, by_key


def canonical_name(raw_name: str | None, text: str, by_key: dict[str, str]) -> str | None:
    raw_key = neighborhood_key(raw_name)
    if raw_key in by_key:
        return by_key[raw_key]

    alias = suggest_canonical_neighborhood(raw_name)
    if alias:
        canonical = by_key.get(neighborhood_key(alias))
        if canonical:
            return canonical

    resolved = resolve_neighborhood(text, raw_name).canonical
    if resolved:
        return by_key.get(neighborhood_key(resolved))
    return None


def calculate_snapshot(now: datetime | None = None) -> list[dict]:
    current = now or datetime.now(timezone.utc)
    snapshot_date = current.astimezone(timezone.utc).date()
    names, by_key = load_catalogue()
    listing_counts: dict[str, int] = defaultdict(int)
    prices: dict[str, list[float]] = defaultdict(list)
    seen: set[str] = set()

    settings = get_settings()
    if settings.database_url is None:
        raise RuntimeError("DATABASE_URL n'est pas configurée.")

    with psycopg.connect(
        settings.database_url.get_secret_value(),
        row_factory=dict_row,
        connect_timeout=10,
    ) as connection:
        with connection.transaction():
            connection.execute("SET TRANSACTION READ ONLY")
            connection.execute("SET LOCAL statement_timeout = '90s'")
            rows = connection.execute(
                """
                SELECT
                    a.id::text AS id,
                    a.url,
                    a.date_publication,
                    a.quartier_zone,
                    a.prix_fcfa,
                    a.superficie_m2,
                    a.texte_nettoye,
                    a.resume_court
                FROM public.annonces AS a
                LEFT JOIN public.admin_announcement_flags AS f
                    ON f.announcement_id = a.id::text
                WHERE COALESCE(f.is_trashed, FALSE) = FALSE
                  AND a.quartier_zone IS NOT NULL
                  AND BTRIM(a.quartier_zone) <> ''
                ORDER BY a.premiere_collecte DESC NULLS LAST, a.id
                """
            ).fetchall()

    for row in rows:
        published = publication_time(row.get("date_publication"))
        if published is None or published > current:
            continue

        text = (row.get("texte_nettoye") or row.get("resume_court") or "").strip()
        raw_neighborhood = row.get("quartier_zone")
        if not sale_eligible(text):
            continue
        if not market_scope_eligible(text, raw_neighborhood):
            continue

        name = canonical_name(raw_neighborhood, text, by_key)
        if not name:
            continue

        identity = (row.get("url") or "").strip() or str(row["id"])
        if identity in seen:
            continue
        seen.add(identity)
        key = neighborhood_key(name)
        listing_counts[key] += 1

        price = row.get("prix_fcfa")
        area = row.get("superficie_m2")
        candidate = SearchCandidate(
            identifier=str(row["id"]),
            text=text,
            neighborhood=name,
            price_fcfa=float(price) if price is not None else None,
            area_m2=float(area) if area is not None else None,
        )
        price_m2 = price_per_square_metre(candidate)
        if price_m2 is not None:
            prices[key].append(price_m2)

    result = []
    for name in names:
        key = neighborhood_key(name)
        values = prices.get(key, [])
        result.append({
            "snapshot_date": snapshot_date,
            "neighborhood_key": key,
            "neighborhood_name": name,
            "median_price_m2_fcfa": round(median(values), 2) if values else None,
            "listing_count": listing_counts.get(key, 0),
            "priced_listing_count": len(values),
        })
    return result


def refresh_snapshot() -> tuple[int, int, int]:
    rows = calculate_snapshot()
    settings = get_settings()
    snapshot_date = rows[0]["snapshot_date"] if rows else datetime.now(timezone.utc).date()
    migration = MIGRATION_PATH.read_text(encoding="utf-8")

    with psycopg.connect(
        settings.database_url.get_secret_value(),
        connect_timeout=10,
    ) as connection:
        with connection.transaction():
            for statement in migration.split(';'):
                if statement.strip():
                    connection.execute(statement)
            connection.executemany(
                """
                INSERT INTO public.market_neighborhood_price_daily (
                    snapshot_date, neighborhood_key, neighborhood_name,
                    median_price_m2_fcfa, listing_count, priced_listing_count,
                    computed_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (snapshot_date, neighborhood_key) DO UPDATE SET
                    neighborhood_name = EXCLUDED.neighborhood_name,
                    median_price_m2_fcfa = EXCLUDED.median_price_m2_fcfa,
                    listing_count = EXCLUDED.listing_count,
                    priced_listing_count = EXCLUDED.priced_listing_count,
                    computed_at = CURRENT_TIMESTAMP
                """,
                [
                    (
                        row["snapshot_date"],
                        row["neighborhood_key"],
                        row["neighborhood_name"],
                        row["median_price_m2_fcfa"],
                        row["listing_count"],
                        row["priced_listing_count"],
                    )
                    for row in rows
                ],
            )

    populated = sum(row["median_price_m2_fcfa"] is not None for row in rows)
    priced = sum(row["priced_listing_count"] for row in rows)
    return len(rows), populated, priced


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    total, populated, priced = refresh_snapshot()
    LOG.info(
        "Snapshot quotidien terminé : %s quartiers, %s avec prix, %s annonces utilisées.",
        total,
        populated,
        priced,
    )


if __name__ == "__main__":
    main()
