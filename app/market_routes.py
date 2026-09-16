"""Statistiques publiques agrégées : aucun contact ni texte d'annonce."""
import psycopg
from fastapi import APIRouter, HTTPException

from app.database import DatabaseNotConfiguredError
from app.market_stats import neighborhood_trends, summarize_market
from app.search_repository import load_recent_candidates
from app.neighborhoods import KNOWN_NEIGHBORHOOD_ALIASES, neighborhood_key

router = APIRouter(prefix='/market', tags=['Accueil'])


@router.get('/stats')
def market_stats() -> dict:
    try:
        # La limite du pool de recherche ne doit pas tronquer les totaux. Les
        # dates publiées sont filtrées avant analyse, indépendamment de la collecte.
        return summarize_market(load_recent_candidates(None, pool_limit=None, publication_days=60))
    except (DatabaseNotConfiguredError, psycopg.Error):
        raise HTTPException(status_code=503, detail='Les chiffres ne sont pas disponibles pour le moment.') from None


@router.get('/neighborhood-trends')
def market_neighborhood_trends() -> dict:
    try:
        # Un trimestre calendaire peut couvrir un peu plus de 90 jours. On charge
        # 120 jours afin de toujours disposer de la période courante complète.
        return neighborhood_trends(load_recent_candidates(None, pool_limit=None, publication_days=120))
    except (DatabaseNotConfiguredError, psycopg.Error):
        raise HTTPException(status_code=503, detail='Les tendances par quartier ne sont pas disponibles pour le moment.') from None


@router.get('/neighborhoods')
def market_neighborhoods() -> list[str]:
    return sorted(set(KNOWN_NEIGHBORHOOD_ALIASES.values()), key=neighborhood_key)
