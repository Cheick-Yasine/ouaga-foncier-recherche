"""Point d'entrée FastAPI."""

from pathlib import Path

import psycopg
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import get_settings
from app.database import DatabaseNotConfiguredError, check_database_connection
from app.search_routes import router as search_router


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
    version="0.3.0",
)
app.include_router(search_router)

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False, response_class=FileResponse)
def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api", tags=["Système"])
def api_information() -> dict[str, str]:
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
