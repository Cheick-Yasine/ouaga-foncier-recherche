"""Statistiques publiques agrégées : aucun contact ni texte d'annonce."""
from copy import deepcopy
from statistics import median
import psycopg
from threading import Lock
from time import monotonic
from typing import Callable, Literal, TypeVar
from fastapi import APIRouter, HTTPException

from app.database import DatabaseNotConfiguredError
from app.market_stats import neighborhood_trends, summarize_market
from app.listing_scope import market_scope_eligible, sale_eligible
from app.search_engine import price_per_square_metre
from app.search_repository import load_market_candidates, load_neighborhood_candidates
from app.neighborhoods import (
    KNOWN_NEIGHBORHOOD_ALIASES,
    neighborhood_key,
    suggest_canonical_neighborhood,
)
from app.neighborhood_geo import location_for

router = APIRouter(prefix='/market', tags=['Accueil'])

# Les statistiques d'accueil changent moins vite que les requêtes utilisateurs.
# Une durée de 6 heures limite les lectures et calculs Neon, au prix d'un
# possible décalage des statistiques après l'ajout de nouvelles annonces.
_MARKET_CACHE_TTL_SECONDS = 6 * 60 * 60.0
_market_cache: dict[tuple, tuple[float, object]] = {}
_market_cache_lock = Lock()
_T = TypeVar("_T")


def _cached_market_result(key: tuple, builder: Callable[[], _T]) -> _T:
    """Renvoie une copie du résultat en cache, ou le calcule une seule fois par clé."""
    now = monotonic()
    with _market_cache_lock:
        cached = _market_cache.get(key)
        if cached is not None and now - cached[0] < _MARKET_CACHE_TTL_SECONDS:
            return deepcopy(cached[1])  # type: ignore[return-value]

        # Calculer sous le verrou évite que plusieurs chargements simultanés
        # déclenchent la même requête coûteuse vers Neon.
        result = builder()
        if len(_market_cache) >= 32:
            _market_cache.clear()
        _market_cache[key] = (monotonic(), deepcopy(result))
        return result


@router.get('/stats')
def market_stats() -> dict:
    def build() -> dict:
        # La limite du pool de recherche ne doit pas tronquer les totaux. Les
        # dates publiées sont filtrées avant analyse, indépendamment de la collecte.
        return summarize_market(load_market_candidates(publication_days=None))

    try:
        return _cached_market_result(("stats",), build)
    except (DatabaseNotConfiguredError, psycopg.Error):
        raise HTTPException(status_code=503, detail='Les chiffres ne sont pas disponibles pour le moment.') from None


@router.get('/neighborhood-trends')
def market_neighborhood_trends(
    period: Literal["7d", "14d", "1m", "2m", "3m", "1y", "3y", "5y", "max"] = "1m",
    aggregation: Literal["day", "week"] = "day",
) -> dict:
    def build() -> dict:
        return neighborhood_trends(
            load_neighborhood_candidates(),
            period=period,
            aggregation=aggregation,
        )

    try:
        return _cached_market_result(("neighborhood-trends", period, aggregation), build)
    except (DatabaseNotConfiguredError, psycopg.Error):
        raise HTTPException(
            status_code=503,
            detail='Les tendances par quartier ne sont pas disponibles pour le moment.',
        ) from None


@router.get('/neighborhoods')
def market_neighborhoods() -> list[str]:
    return sorted(set(KNOWN_NEIGHBORHOOD_ALIASES.values()), key=neighborhood_key)


@router.get('/neighborhood-location')
def market_neighborhood_location(name: str) -> dict | None:
    """Retourne uniquement le repère du référentiel cartographique embarqué.

    La carte, les distances et les sélections utilisent ainsi exactement la
    même paire latitude/longitude. Aucun géocodage à la volée ne peut injecter
    un second point différent après l'affichage initial.
    """
    canonical = next(
        (value for key, value in KNOWN_NEIGHBORHOOD_ALIASES.items()
         if neighborhood_key(key) == neighborhood_key(name)), None,
    )
    if not canonical:
        return None
    point = location_for(canonical)
    if not point:
        return None
    return {
        'name': point['name'], 'latitude': point['latitude'],
        'longitude': point['longitude'], 'source': point['source'],
        'attribution': point['attribution'], 'license_url': point['license_url'],
    }


def _neighborhood_median_prices() -> dict[str, float]:
    """Prix médian au m² par quartier, sur les annonces de vente éligibles."""
    medians: dict[str, list[float]] = {}
    seen: set[str] = set()
    for candidate in load_market_candidates(publication_days=None):
        if (
            not candidate.neighborhood
            or not sale_eligible(candidate.text)
            or not market_scope_eligible(candidate.text, candidate.neighborhood)
        ):
            continue
        identity = candidate.url or candidate.identifier
        if identity in seen:
            continue
        seen.add(identity)
        neighborhood = (
            suggest_canonical_neighborhood(candidate.neighborhood)
            or candidate.neighborhood.strip()
        )
        unit_price = price_per_square_metre(candidate)
        if not neighborhood or unit_price is None:
            continue
        medians.setdefault(neighborhood_key(neighborhood), []).append(unit_price)
    return {
        key: round(median(values), 2)
        for key, values in medians.items()
        if values
    }


@router.get('/neighborhood-locations')
def market_neighborhood_locations() -> list[dict]:
    """Repères des quartiers et prix médians au m² pour la carte."""
    def build() -> list[dict]:
        median_prices = _neighborhood_median_prices()
        names = sorted(set(KNOWN_NEIGHBORHOOD_ALIASES.values()), key=neighborhood_key)
        locations = []
        seen = set()
        for name in names:
            point = location_for(name)
            if not point:
                continue
            key = neighborhood_key(point['name'])
            if key in seen:
                continue
            seen.add(key)
            locations.append({
                'name': point['name'],
                'latitude': point['latitude'],
                'longitude': point['longitude'],
                'prix_median_m2_fcfa': median_prices.get(key),
                'source': point['source'],
                'attribution': point['attribution'],
                'license_url': point['license_url'],
            })
        return locations

    try:
        return _cached_market_result(("neighborhood-locations",), build)
    except (DatabaseNotConfiguredError, psycopg.Error):
        raise HTTPException(
            status_code=503,
            detail='Les repères et prix médians des quartiers ne sont pas disponibles.',
        ) from None
