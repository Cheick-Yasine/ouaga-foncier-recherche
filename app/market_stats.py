"""Chiffres descriptifs des publications datées, sans estimation immobilière."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import re
from statistics import fmean
from typing import Iterable

from app.listing_scope import market_scope_eligible, sale_eligible
from app.neighborhoods import CITY_LEVEL_AREAS, neighborhood_key
from app.search_engine import SearchCandidate, price_per_square_metre


def publication_time(value: str | None) -> datetime | None:
    """Normalise une date ISO ou un timestamp Unix Facebook/Apify."""
    if not value:
        return None

    text = value.strip()

    # Certains exports Apify stockent la date Facebook comme timestamp Unix
    # en secondes (10 chiffres) ou en millisecondes (13 chiffres).
    if re.fullmatch(r"\d{10}", text):
        try:
            return datetime.fromtimestamp(int(text), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None

    if re.fullmatch(r"\d{13}", text):
        try:
            return datetime.fromtimestamp(int(text) / 1000, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None

    try:
        parsed = datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def summarize_market(candidates: Iterable[SearchCandidate], *, now: datetime | None = None) -> dict:
    current = now or datetime.now(timezone.utc)
    start = current - timedelta(days=30)
    week_end = (current - timedelta(days=current.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = week_end - timedelta(days=28)
    pool, seen = [], set()
    for candidate in candidates:
        published = publication_time(candidate.publication_label)
        if published is None or not min(start, week_start) <= published <= current:
            continue
        if (
            not sale_eligible(candidate.text)
            or not market_scope_eligible(
                candidate.text,
                candidate.neighborhood,
            )
        ):
            continue
        identity = candidate.url or candidate.identifier
        if identity in seen:
            continue
        seen.add(identity)
        pool.append(candidate)
    rows = [c for c in pool if publication_time(c.publication_label) >= start]
    units = [price_per_square_metre(c) for c in rows]
    units = [unit for unit in units if unit is not None]
    neighborhoods = Counter(c.neighborhood for c in rows if c.neighborhood and c.neighborhood not in CITY_LEVEL_AREAS)
    top = sorted(neighborhoods, key=lambda n: (-neighborhoods[n], neighborhood_key(n)))
    return {
        'annonces_30_jours': len(rows),
        'prix_m2_moyen_fcfa': round(fmean(units), 2) if units else None,
        'annonces_avec_prix_m2': len(units),
        'quartier_le_plus_represente': top[0] if top else None,
        'annonces_quartier_principal': neighborhoods[top[0]] if top else 0,
        'depuis': start.isoformat(), 'jusqu_a': current.isoformat(),
        'perimetre': 'Ouagadougou et environs', 'date_utilisee': 'date_publication',
        'semaines': weekly_market(pool, week_start),
    }


def weekly_market(candidates, start):
    weeks = []
    for index in range(4):
        begin, end = start + timedelta(days=7*index), start + timedelta(days=7*(index+1))
        rows = [c for c in candidates if begin <= publication_time(c.publication_label) < end]
        by_type = {}
        for kind in ('tous', 'parcelle', 'terrain', 'maison'):
            selected = rows if kind == 'tous' else [c for c in rows if c.property_type == kind]
            prices = [p for c in selected if (p := price_per_square_metre(c)) is not None]
            by_type[kind] = {'annonces': len(selected), 'prix_m2': round(fmean(prices), 2) if prices else None, 'prix_renseignes': len(prices)}
        weeks.append({'debut': begin.date().isoformat(), 'fin': (end-timedelta(days=1)).date().isoformat(), 'types': by_type})
    return weeks


def _main_activity_cluster(
    candidates: list[SearchCandidate],
    *,
    gap_days: int = 60,
) -> tuple[list[SearchCandidate], int]:
    """Retient la concentration temporelle principale de la base."""
    if not candidates:
        return [], 0

    ordered = sorted(
        candidates,
        key=lambda candidate: publication_time(candidate.publication_label),
    )
    clusters: list[list[SearchCandidate]] = [[]]
    previous = None

    for candidate in ordered:
        published = publication_time(candidate.publication_label)
        if (
            clusters[-1]
            and previous is not None
            and published is not None
            and (published.date() - previous.date()).days > gap_days
        ):
            clusters.append([])
        clusters[-1].append(candidate)
        previous = published

    largest = max(len(cluster) for cluster in clusters)
    meaningful = [
        cluster
        for cluster in clusters
        if len(cluster) >= max(5, round(largest * 0.25))
    ]
    selected = max(
        meaningful or clusters,
        key=lambda cluster: (
            len(cluster),
            publication_time(cluster[-1].publication_label),
        ),
    )
    return selected, len(candidates) - len(selected)


def neighborhood_trends(
    candidates: Iterable[SearchCandidate],
    *,
    now: datetime | None = None,
    period: str | None = None,
    aggregation: str = "day",
) -> dict:
    """Top 5 quartiers sur une période glissante, agrégés par jour ou semaine.

    Sans période explicite, conserve le comportement historique utilisé par
    les appels internes/tests plus anciens : la concentration d'activité
    principale est retenue. L'API publique fournit toujours une période.
    """

    period_days = {
        "7d": 7,
        "14d": 14,
        "1m": 30,
        "2m": 60,
        "3m": 90,
        "1y": 365,
        "max": None,
    }
    if period is not None and period not in period_days:
        raise ValueError(f"Période inconnue : {period}")
    if aggregation not in {"day", "week"}:
        raise ValueError(f"Agrégation inconnue : {aggregation}")

    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    pool: list[SearchCandidate] = []
    seen: set[str] = set()

    for candidate in candidates:
        published = publication_time(candidate.publication_label)
        if published is None or published > current:
            continue
        if not sale_eligible(candidate.text) or not market_scope_eligible(
            candidate.text,
            candidate.neighborhood,
        ):
            continue
        if (
            not candidate.neighborhood
            or candidate.neighborhood in CITY_LEVEL_AREAS
        ):
            continue

        identity = candidate.url or candidate.identifier
        if identity in seen:
            continue
        seen.add(identity)
        pool.append(candidate)

    ignored_isolated = 0
    legacy_window = period is None
    effective_period = period or "max"

    if legacy_window:
        pool, ignored_isolated = _main_activity_cluster(pool)

    if not pool:
        return {
            "date_utilisee": "date_publication",
            "granularite_source": "jour",
            "periode": effective_period,
            "agregation": aggregation,
            "debut": None,
            "fin": None,
            "annonces_isolees_ignorees": ignored_isolated,
            "types": {
                kind: {"total_annonces": 0, "quartiers": []}
                for kind in ("tous", "parcelle", "terrain", "maison")
            },
        }

    dated = [
        (
            candidate,
            publication_time(candidate.publication_label).astimezone(
                timezone.utc
            ),
        )
        for candidate in pool
    ]
    latest = max(published for _, published in dated).date()
    oldest = min(published for _, published in dated).date()

    if legacy_window:
        start_date = oldest
        end_date = latest
    else:
        days = period_days[effective_period]
        if days is None:
            start_date = oldest
            end_date = latest
        else:
            end_date = current.date()
            start_date = max(
                oldest,
                end_date - timedelta(days=days - 1),
            )

    selected_pool = [
        candidate
        for candidate, published in dated
        if start_date <= published.date() <= end_date
    ]

    def bucket_bounds(day):
        if aggregation == "day":
            return day, day
        monday = day - timedelta(days=day.weekday())
        sunday = monday + timedelta(days=6)
        return max(monday, start_date), min(sunday, end_date)

    by_type = {}
    for kind in ("tous", "parcelle", "terrain", "maison"):
        selected = (
            selected_pool
            if kind == "tous"
            else [
                candidate
                for candidate in selected_pool
                if candidate.property_type == kind
            ]
        )
        totals = Counter(
            candidate.neighborhood
            for candidate in selected
            if candidate.neighborhood
        )
        names = sorted(
            totals,
            key=lambda name: (-totals[name], neighborhood_key(name)),
        )[:5]

        counts = Counter()
        for candidate in selected:
            published = publication_time(candidate.publication_label)
            begin, end = bucket_bounds(published.date())
            counts[
                (
                    begin.isoformat(),
                    end.isoformat(),
                    candidate.neighborhood,
                )
            ] += 1

        buckets: list[tuple[str, str]] = []
        cursor = start_date
        while cursor <= end_date:
            begin, end = bucket_bounds(cursor)
            key = (begin.isoformat(), end.isoformat())
            if not buckets or buckets[-1] != key:
                buckets.append(key)
            cursor = (
                cursor + timedelta(days=1)
                if aggregation == "day"
                else end + timedelta(days=1)
            )

        by_type[kind] = {
            "total_annonces": len(selected),
            "quartiers": [
                {
                    "nom": name,
                    "total": totals[name],
                    "part_pct": round(
                        (totals[name] / len(selected)) * 100,
                        1,
                    )
                    if selected
                    else 0.0,
                    "points": [
                        {
                            "date": begin,
                            "debut": begin,
                            "fin": end,
                            "annonces": counts[(begin, end, name)],
                        }
                        for begin, end in buckets
                    ],
                }
                for name in names
            ],
        }

    return {
        "date_utilisee": "date_publication",
        "granularite_source": "jour",
        "periode": effective_period,
        "agregation": aggregation,
        "debut": start_date.isoformat(),
        "fin": end_date.isoformat(),
        "annonces_isolees_ignorees": ignored_isolated,
        "types": by_type,
    }

