"""Tests du socle FastAPI."""

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


client = TestClient(app)


def test_root_serves_search_interface() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Foncier Ouaga" in response.text
    assert 'id="search-form"' in response.text
    assert 'id="max-age-days"' in response.text
    assert '<option value="30" selected>1 mois</option>' in response.text


def test_api_information() -> None:
    response = client.get("/api")

    assert response.status_code == 200
    assert response.json()["documentation"] == "/docs"


def test_static_assets_are_available() -> None:
    css = client.get("/static/styles.css")
    javascript = client.get("/static/app.js")

    assert css.status_code == 200
    assert "--accent" in css.text
    assert javascript.status_code == 200
    assert 'fetch("/search"' in javascript.text
    assert "AbortController" in javascript.text
    assert "50000" in javascript.text
    assert "max_age_days:Number(maxAgeInput.value)" in javascript.text
    assert "emptyState" not in javascript.text


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_database_health_without_database_url(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()

    response = client.get("/health/database")

    assert response.status_code == 503
    assert "DATABASE_URL" in response.json()["detail"]
    get_settings.cache_clear()
