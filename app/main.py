"""Point d'entrée FastAPI."""

import psycopg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.config import get_settings
from app.database import DatabaseNotConfiguredError, check_database_connection\nfrom app.search_routes import router as search_router


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str


class DatabaseHealthResponse(BaseModel):
    status: str
    provider: str


app = FastAPI(
    title="Ouaga Foncier Recherche",
    description="Recherche intelligente d'annonces immobilières récentes.",
    version="0.1.0",
)


@app.get("/", tags=["Système"])
def root() -> dict[str, str]:
    return {
        "message": "API Ouaga Foncier Recherche",
        "documentation": "/docs",
    }


@app.get("/health", response_model=HealthResponse, tags=["Système"])
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        environment=settings.app_env,
    )


@app.get(
    "/health/database",
    response_model=DatabaseHealthResponse,
    tags=["Système"],
)
def database_health() -> DatabaseHealthResponse:
    try:
        is_available = check_database_connection()
    except DatabaseNotConfiguredError as error:
        raise HTTPException(status_code=503, detail=str(error)) from None
    except psycopg.Error:
        raise HTTPException(
            status_code=503,
            detail="La connexion à Neon a échoué. Vérifiez DATABASE_URL.",
        ) from None

    if not is_available:
        raise HTTPException(
            status_code=503,
            detail="Neon a répondu, mais le contrôle SELECT 1 a échoué.",
        )

    return DatabaseHealthResponse(status="ok", provider="Neon PostgreSQL")
