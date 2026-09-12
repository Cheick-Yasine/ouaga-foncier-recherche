"""Chiffres descriptifs des publications datées, sans estimation immobilière."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from statistics import fmean
from typing import Iterable

from app.listing_scope import sale_eligible, within_ouagadougou
from app.neighborhoods import CITY_LEVEL_AREAS, neighborhood_key
from app.search_engine import SearchCandidate, price_per_square_metre


def publication_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
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
        if not sale_eligible(candidate.text) or not within_ouagadougou(candidate.text, candidate.neighborhood):
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
        'perimetre': 'Ouagadougou', 'date_utilisee': 'date_publication',
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
