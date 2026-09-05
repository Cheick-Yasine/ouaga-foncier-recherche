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
    assert "Trouvez les annonces qui vous correspondent." in response.text
    assert "<th>Contact</th>" in response.text
    assert "<th>Prix / m²</th>" in response.text
    assert '<label for="auth-name">Nom</label>' in response.text
    assert 'minlength="4"' in response.text
    assert "Recommandation personnalisée" not in response.text
    assert "Notre recommandation" not in response.text
    assert "Adresse e-mail" not in response.text
    assert "Critères compris" not in response.text
    assert "Comparer les annonces" not in response.text
    assert "Annonces publiées par des tiers." not in response.text
    assert 'id="result-count"' not in response.text


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
    assert "AbortController" not in javascript.text
    assert "50000" not in javascript.text
    assert "max_age_days:Number(maxAgeInput.value)" in javascript.text
    assert "emptyState" not in javascript.text
    assert "function appendContact" in javascript.text
    assert "function formatUnitPrice" in javascript.text
    assert "currentUser.name" in javascript.text
    assert "prix au m² le plus avantageux" not in javascript.text
    assert "resultCount" not in javascript.text
    assert "criteriaSummary" not in javascript.text


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
