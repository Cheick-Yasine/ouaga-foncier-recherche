"""Statistiques publiques agrégées : aucun contact ni texte d'annonce."""
import psycopg
from fastapi import APIRouter, HTTPException

from app.database import DatabaseNotConfiguredError
from app.market_stats import summarize_market
from app.search_repository import load_recent_candidates

router = APIRouter(prefix='/market', tags=['Accueil'])


@router.get('/stats')
def market_stats() -> dict:
    try:
        # La limite du pool de recherche ne doit pas tronquer les totaux. Les
        # dates publiées sont filtrées avant analyse, indépendamment de la collecte.
        return summarize_market(load_recent_candidates(None, pool_limit=None, publication_days=30))
    except (DatabaseNotConfiguredError, psycopg.Error):
        raise HTTPException(status_code=503, detail='Les chiffres ne sont pas disponibles pour le moment.') from None
