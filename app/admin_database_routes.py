"""Routes de consultation de la base réservées aux administrateurs."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import psycopg
from fastapi import APIRouter, Cookie, HTTPException
from pydantic import BaseModel, Field
from psycopg.rows import dict_row

from app.auth import SESSION_COOKIE, AuthenticatedUser, get_session_user
from app.config import get_settings
from app.database import DatabaseNotConfiguredError
from app.sql_assistant import run_sql_assistant
from app.sql_reader import SQLReadError


router = APIRouter(prefix="/admin/database", tags=["Administration"])


QUESTIONS = [
    ("recentes", "Afficher les 15 dernières annonces", "Dernières annonces", "recent"),
    ("moins_1m", "Afficher les annonces à moins de 1 million FCFA", "Moins de 1 million", "prix"),
    ("plus_100m", "Afficher les annonces à plus de 100 millions FCFA", "Plus de 100 millions", "prix"),
    ("moins_5m", "Afficher les annonces à moins de 5 millions FCFA", "Moins de 5 millions", "prix"),
    ("entre_5_10m", "Afficher les annonces entre 5 et 10 millions FCFA", "5 à 10 millions", "prix"),
    ("entre_10_50m", "Afficher les annonces entre 10 et 50 millions FCFA", "10 à 50 millions", "prix"),
    ("entre_50_100m", "Afficher les annonces entre 50 et 100 millions FCFA", "50 à 100 millions", "prix"),
    ("plus_1000m2", "Afficher les annonces de plus de 1 000 m²", "Plus de 1 000 m²", "superficie"),
    ("moins_200m2", "Afficher les annonces de moins de 200 m²", "Moins de 200 m²", "superficie"),
    ("entre_200_500m2", "Afficher les annonces entre 200 et 500 m²", "200 à 500 m²", "superficie"),
    ("prix_stats", "Donner les statistiques générales de prix", "Statistiques de prix", "statistiques"),
    ("surface_stats", "Donner les statistiques générales de superficie", "Statistiques de superficie", "statistiques"),
    ("sans_prix", "Afficher les annonces sans prix", "Prix manquant", "qualité"),
    ("sans_superficie", "Afficher les annonces sans superficie", "Superficie manquante", "qualité"),
    ("sans_prix_superficie", "Afficher les annonces sans prix et sans superficie", "Prix et superficie manquants", "qualité"),
    ("avec_document", "Afficher les annonces avec document renseigné", "Document renseigné", "documents"),
    ("sans_document", "Afficher les annonces sans document", "Document manquant", "documents"),
    ("attestation", "Afficher les annonces mentionnant une attestation", "Attestation", "documents"),
    ("puh", "Afficher les annonces mentionnant un PUH", "PUH", "documents"),
    ("eau", "Afficher les annonces avec eau renseignée", "Eau", "caractéristiques"),
    ("electricite", "Afficher les annonces avec électricité renseignée", "Électricité", "caractéristiques"),
    ("terrains", "Afficher uniquement les terrains", "Terrains", "types"),
    ("parcelles", "Afficher uniquement les parcelles", "Parcelles", "types"),
    ("maisons", "Afficher uniquement les maisons", "Maisons", "types"),
    ("comptage_types", "Compter les annonces par type de bien", "Répartition par type", "statistiques"),
    ("comptage_quartiers", "Compter les annonces par quartier", "Répartition par quartier", "statistiques"),
    ("quartiers_plus_annonces", "Donner les 20 quartiers avec le plus d'annonces", "Quartiers les plus représentés", "statistiques"),
    ("saaba", "Afficher les annonces de Saaba", "Saaba", "géographie"),
    ("pabre", "Afficher les annonces de Pabré", "Pabré", "géographie"),
    ("koubri", "Afficher les annonces de Koubri", "Koubri", "géographie"),
    ("aujourdhui", "Compter les annonces collectées aujourd'hui", "Collecte du jour", "dates"),
    ("hier", "Compter les annonces collectées hier", "Collecte d'hier", "dates"),
    ("semaine", "Compter les annonces collectées cette semaine", "Collecte de la semaine", "dates"),
    ("plus_grandes", "Afficher les 20 plus grandes superficies", "Plus grandes superficies", "superficie"),
    ("plus_cheres", "Afficher les 20 annonces les plus chères", "Plus chères", "prix"),
    ("moins_cheres", "Afficher les 20 annonces les moins chères", "Moins chères", "prix"),
    ("derniere_publication", "Afficher la date de publication la plus récente", "Dernière publication", "dates"),
]

ANNONCE_SQL = """SELECT a.id, a.premiere_collecte, a.date_publication, a.type_bien_normalise, a.quartier_zone,
    a.prix_fcfa, a.superficie_m2, a.statut_document, a.resume_court, a.texte_nettoye,
    COALESCE(f.is_featured, FALSE) AS is_featured
    FROM public.annonces a
    LEFT JOIN public.admin_announcement_flags f ON f.announcement_id = a.id::text
    WHERE COALESCE(f.is_trashed, FALSE) = FALSE"""

SQL = {
    "recentes": ANNONCE_SQL + " ORDER BY is_featured DESC, premiere_collecte DESC NULLS LAST, id DESC LIMIT 15",
    "moins_1m": ANNONCE_SQL + " AND prix_fcfa IS NOT NULL AND prix_fcfa < 1000000 ORDER BY prix_fcfa ASC LIMIT 100",
    "plus_100m": ANNONCE_SQL + " AND prix_fcfa IS NOT NULL AND prix_fcfa > 100000000 ORDER BY prix_fcfa DESC LIMIT 100",
    "moins_5m": ANNONCE_SQL + " AND prix_fcfa IS NOT NULL AND prix_fcfa < 5000000 ORDER BY prix_fcfa ASC LIMIT 100",
    "entre_5_10m": ANNONCE_SQL + " AND prix_fcfa BETWEEN 5000000 AND 10000000 ORDER BY prix_fcfa ASC LIMIT 100",
    "entre_10_50m": ANNONCE_SQL + " AND prix_fcfa BETWEEN 10000000 AND 50000000 ORDER BY prix_fcfa ASC LIMIT 100",
    "entre_50_100m": ANNONCE_SQL + " AND prix_fcfa BETWEEN 50000000 AND 100000000 ORDER BY prix_fcfa ASC LIMIT 100",
    "plus_1000m2": ANNONCE_SQL + " AND superficie_m2 > 1000 ORDER BY superficie_m2 DESC LIMIT 100",
    "moins_200m2": ANNONCE_SQL + " AND superficie_m2 IS NOT NULL AND superficie_m2 < 200 ORDER BY superficie_m2 ASC LIMIT 100",
    "entre_200_500m2": ANNONCE_SQL + " AND superficie_m2 BETWEEN 200 AND 500 ORDER BY superficie_m2 ASC LIMIT 100",
    "prix_stats": """SELECT COUNT(*) AS total, COUNT(prix_fcfa) AS avec_prix,
        ROUND(AVG(prix_fcfa)) AS prix_moyen, MIN(prix_fcfa) AS prix_min,
        MAX(prix_fcfa) AS prix_max,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY prix_fcfa) AS prix_median
        FROM public.annonces""",
    "surface_stats": """SELECT COUNT(*) AS total, COUNT(superficie_m2) AS avec_superficie,
        ROUND(AVG(superficie_m2)::numeric, 2) AS superficie_moyenne,
        MIN(superficie_m2) AS superficie_min, MAX(superficie_m2) AS superficie_max,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY superficie_m2) AS superficie_mediane
        FROM public.annonces""",
    "sans_prix": ANNONCE_SQL + " AND prix_fcfa IS NULL ORDER BY premiere_collecte DESC NULLS LAST LIMIT 100",
    "sans_superficie": ANNONCE_SQL + " AND superficie_m2 IS NULL ORDER BY premiere_collecte DESC NULLS LAST LIMIT 100",
    "sans_prix_superficie": ANNONCE_SQL + " AND prix_fcfa IS NULL AND superficie_m2 IS NULL ORDER BY premiere_collecte DESC NULLS LAST LIMIT 100",
    "avec_document": ANNONCE_SQL + " AND statut_document IS NOT NULL AND LOWER(statut_document) NOT IN ('non_precise','non_precisee') ORDER BY premiere_collecte DESC NULLS LAST LIMIT 100",
    "sans_document": ANNONCE_SQL + " AND (statut_document IS NULL OR LOWER(statut_document) IN ('non_precise','non_precisee')) ORDER BY premiere_collecte DESC NULLS LAST LIMIT 100",
    "attestation": ANNONCE_SQL + " AND LOWER(COALESCE(statut_document,'')) LIKE '%attestation%' ORDER BY premiere_collecte DESC NULLS LAST LIMIT 100",
    "puh": ANNONCE_SQL + " AND LOWER(COALESCE(statut_document,'') || ' ' || COALESCE(texte_nettoye,'')) LIKE '%puh%' ORDER BY premiere_collecte DESC NULLS LAST LIMIT 100",
    "eau": ANNONCE_SQL + " AND LOWER(COALESCE(texte_nettoye,'')) LIKE '%eau%' ORDER BY premiere_collecte DESC NULLS LAST LIMIT 100",
    "electricite": ANNONCE_SQL + " AND LOWER(COALESCE(texte_nettoye,'')) LIKE '%electric%' ORDER BY premiere_collecte DESC NULLS LAST LIMIT 100",
    "terrains": ANNONCE_SQL + " AND type_bien_normalise = 'terrain' ORDER BY premiere_collecte DESC NULLS LAST LIMIT 100",
    "parcelles": ANNONCE_SQL + " AND type_bien_normalise = 'parcelle' ORDER BY premiere_collecte DESC NULLS LAST LIMIT 100",
    "maisons": ANNONCE_SQL + " AND type_bien_normalise = 'maison' ORDER BY premiere_collecte DESC NULLS LAST LIMIT 100",
    "comptage_types": """SELECT COALESCE(type_bien_normalise,'non_precise') AS type_bien, COUNT(*) AS total
        FROM public.annonces a WHERE NOT EXISTS (SELECT 1 FROM public.admin_announcement_flags f WHERE f.announcement_id=a.id::text AND f.is_trashed) GROUP BY type_bien_normalise ORDER BY total DESC""",
    "comptage_quartiers": """SELECT COALESCE(quartier_zone,'non_precise') AS quartier, COUNT(*) AS total
        FROM public.annonces a WHERE NOT EXISTS (SELECT 1 FROM public.admin_announcement_flags f WHERE f.announcement_id=a.id::text AND f.is_trashed) GROUP BY quartier_zone ORDER BY total DESC""",
    "quartiers_plus_annonces": """SELECT COALESCE(quartier_zone,'non_precise') AS quartier, COUNT(*) AS total
        FROM public.annonces a WHERE NOT EXISTS (SELECT 1 FROM public.admin_announcement_flags f WHERE f.announcement_id=a.id::text AND f.is_trashed) GROUP BY quartier_zone ORDER BY total DESC LIMIT 20""",
    "saaba": ANNONCE_SQL + " AND LOWER(COALESCE(quartier_zone,'')) LIKE '%saaba%' ORDER BY premiere_collecte DESC NULLS LAST LIMIT 100",
    "pabre": ANNONCE_SQL + " AND LOWER(COALESCE(quartier_zone,'')) LIKE '%pabre%' ORDER BY premiere_collecte DESC NULLS LAST LIMIT 100",
    "koubri": ANNONCE_SQL + " AND LOWER(COALESCE(quartier_zone,'')) LIKE '%koubri%' ORDER BY premiere_collecte DESC NULLS LAST LIMIT 100",
    "aujourdhui": "SELECT COUNT(*) AS total FROM public.annonces WHERE premiere_collecte >= CURRENT_DATE AND premiere_collecte < CURRENT_DATE + INTERVAL '1 day'",
    "hier": "SELECT COUNT(*) AS total FROM public.annonces WHERE premiere_collecte >= CURRENT_DATE - INTERVAL '1 day' AND premiere_collecte < CURRENT_DATE",
    "semaine": "SELECT COUNT(*) AS total FROM public.annonces WHERE premiere_collecte >= date_trunc('week', CURRENT_TIMESTAMP)",
    "plus_grandes": ANNONCE_SQL + " AND superficie_m2 IS NOT NULL ORDER BY superficie_m2 DESC LIMIT 20",
    "plus_cheres": ANNONCE_SQL + " AND prix_fcfa IS NOT NULL ORDER BY prix_fcfa DESC LIMIT 20",
    "moins_cheres": ANNONCE_SQL + " AND prix_fcfa IS NOT NULL ORDER BY prix_fcfa ASC LIMIT 20",
    "derniere_publication": "SELECT MAX(CASE WHEN date_publication LIKE '__/__/____' THEN TO_DATE(date_publication, 'DD/MM/YYYY') WHEN date_publication LIKE '____-__-__%' THEN SUBSTRING(date_publication, 1, 10)::date ELSE NULL END) AS derniere_date_publication FROM public.annonces",
}


class QuestionRequest(BaseModel):
    question: str = Field(min_length=2, max_length=6000)


def _require_admin(session_token: str | None) -> AuthenticatedUser:
    try:
        user = get_session_user(session_token)
    except (DatabaseNotConfiguredError, psycopg.Error):
        raise HTTPException(status_code=503, detail="La base de comptes est temporairement indisponible.") from None
    if user is None:
        raise HTTPException(status_code=401, detail="Connexion requise.")
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Accès administrateur requis.")
    return user


def _db_url() -> str:
    settings = get_settings()
    if settings.database_url is None:
        raise DatabaseNotConfiguredError("DATABASE_URL n'est pas configurée.")
    return settings.database_url.get_secret_value()


def _execute(sql: str) -> list[dict[str, Any]]:
    try:
        with psycopg.connect(_db_url(), row_factory=dict_row) as connection:
            with connection.transaction():
                connection.execute("SET TRANSACTION READ ONLY")
                connection.execute("SET LOCAL statement_timeout = '20s'")
                return [dict(row) for row in connection.execute(sql).fetchall()]
    except psycopg.Error:
        raise HTTPException(status_code=503, detail="La consultation de Neon a échoué.") from None


def _overview() -> dict[str, Any]:
    rows = _execute("""SELECT COUNT(*) AS total, COUNT(prix_fcfa) AS avec_prix,
        COUNT(superficie_m2) AS avec_superficie,
        COUNT(*) FILTER (WHERE type_bien_normalise='terrain') AS terrains,
        COUNT(*) FILTER (WHERE type_bien_normalise='parcelle') AS parcelles,
        COUNT(*) FILTER (WHERE type_bien_normalise='maison') AS maisons,
        MAX(premiere_collecte) AS derniere_collecte
        FROM public.annonces""")
    return rows[0]


@router.get("/overview")
def overview(session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> dict[str, Any]:
    _require_admin(session_token)
    return _overview()


@router.get("/recent")
def recent(session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> dict[str, Any]:
    _require_admin(session_token)
    return {"title": "Les 15 dernières annonces", "rows": _execute(SQL["recentes"])}


@router.get("/questions")
def questions(session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> dict[str, Any]:
    _require_admin(session_token)
    return {"questions": [{"id": q[0], "label": q[1], "title": q[2], "category": q[3]} for q in QUESTIONS]}


@router.post("/question")
async def custom_question(payload: QuestionRequest, session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> dict[str, Any]:
    _require_admin(session_token)
    try:
        outcome = await run_sql_assistant(payload.question, [], max_age_days=3650)
        return {
            "answer": outcome.answer,
            "rows": outcome.results,
            "mode": outcome.mode,
            "data_used": outcome.data_used,
        }
    except (SQLReadError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


@router.post("/run/{question_id}")
def run_question(question_id: str, session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> dict[str, Any]:
    _require_admin(session_token)
    sql = SQL.get(question_id)
    if sql is None:
        raise HTTPException(status_code=404, detail="Question inconnue.")
    return {"question_id": question_id, "rows": _execute(sql)}


class AnnouncementFlagRequest(BaseModel):
    trashed: bool | None = None
    featured: bool | None = None
    priority: int = Field(default=0, ge=0, le=1000)
    note: str | None = Field(default=None, max_length=1000)

class ManualAnnouncementRequest(BaseModel):
    texte: str = Field(min_length=3, max_length=20000)
    url: str | None = Field(default=None, max_length=2000)
    type_bien: str = Field(default="parcelle", min_length=3, max_length=40)
    quartier: str | None = Field(default=None, max_length=200)
    prix_fcfa: float | None = Field(default=None, ge=0)
    superficie_m2: float | None = Field(default=None, ge=0)
    document: str | None = Field(default=None, max_length=200)
    contact: str | None = Field(default=None, max_length=500)

@router.get("/trash")
def trash(session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> dict[str, Any]:
    _require_admin(session_token)
    return {"rows": _execute("""SELECT a.id::text AS id, a.premiere_collecte, a.date_publication,
        a.type_bien_normalise, a.quartier_zone, a.prix_fcfa, a.superficie_m2,
        a.statut_document, a.resume_court, a.texte_nettoye
        FROM public.annonces a
        JOIN public.admin_announcement_flags f ON f.announcement_id = a.id::text
        WHERE f.is_trashed = TRUE ORDER BY f.updated_at DESC LIMIT 200""")}

@router.get("/featured")
def featured(session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> dict[str, Any]:
    _require_admin(session_token)
    return {"rows": _execute("""SELECT a.id::text AS id, a.premiere_collecte, a.date_publication,
        a.type_bien_normalise, a.quartier_zone, a.prix_fcfa, a.superficie_m2,
        a.statut_document, a.resume_court, a.texte_nettoye, f.featured_priority
        FROM public.annonces a
        JOIN public.admin_announcement_flags f ON f.announcement_id = a.id::text
        WHERE f.is_featured = TRUE AND f.is_trashed = FALSE
        ORDER BY f.featured_priority DESC, a.premiere_collecte DESC LIMIT 200""")}

@router.post("/flag/{announcement_id}")
def flag_announcement(announcement_id: str, payload: AnnouncementFlagRequest,
                      session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> dict[str, Any]:
    _require_admin(session_token)
    safe_id = announcement_id.replace("'", "''")
    check = _execute("SELECT id::text AS id FROM public.annonces WHERE id::text = '" + safe_id + "' UNION ALL SELECT id::text FROM public.admin_added_annonces WHERE id::text = '" + safe_id + "' LIMIT 1")
    if not check:
        raise HTTPException(status_code=404, detail="Annonce introuvable.")
    with psycopg.connect(_db_url()) as connection:
        connection.execute("""INSERT INTO public.admin_announcement_flags
            (announcement_id, is_trashed, is_featured, featured_priority, note)
            VALUES (%s, COALESCE(%s,FALSE), COALESCE(%s,FALSE), %s, %s)
            ON CONFLICT (announcement_id) DO UPDATE SET
              is_trashed=COALESCE(EXCLUDED.is_trashed, admin_announcement_flags.is_trashed),
              is_featured=COALESCE(EXCLUDED.is_featured, admin_announcement_flags.is_featured),
              featured_priority=EXCLUDED.featured_priority, note=EXCLUDED.note, updated_at=CURRENT_TIMESTAMP""",
            (announcement_id, payload.trashed, payload.featured, payload.priority, payload.note))
    return {"ok": True, "id": announcement_id}

@router.delete("/trash/{announcement_id}")
def restore_announcement(announcement_id: str, session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> dict[str, Any]:
    _require_admin(session_token)
    with psycopg.connect(_db_url()) as connection:
        connection.execute("UPDATE public.admin_announcement_flags SET is_trashed=FALSE, updated_at=CURRENT_TIMESTAMP WHERE announcement_id=%s", (announcement_id,))
    return {"ok": True, "id": announcement_id}

@router.post("/add")
def add_manual_announcement(payload: ManualAnnouncementRequest,
                            session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> dict[str, Any]:
    user = _require_admin(session_token)
    announcement_id = str(uuid4())
    with psycopg.connect(_db_url()) as connection:
        connection.execute("""INSERT INTO public.admin_added_annonces
            (id,url,date_publication,type_bien_normalise,quartier_zone,superficie_m2,prix_fcfa,
             statut_document,contacts_whatsapp,resume_court,texte_nettoye,created_by)
            VALUES (%s,%s,CURRENT_DATE::text,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (announcement_id, payload.url, payload.type_bien.strip().lower(), payload.quartier,
             payload.superficie_m2, payload.prix_fcfa, payload.document, payload.contact,
             payload.texte[:500], payload.texte, user.id))
    return {"ok": True, "id": announcement_id}
