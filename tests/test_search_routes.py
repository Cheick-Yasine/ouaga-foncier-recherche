"""Tests des routes de recherche."""

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_interpret_search_description() -> None:
    response = client.post(
        "/search/interpret",
        json={
            "description": (
                "Je cherche une parcelle à Saaba de 400 m² "
                "avec un budget maximum de 8 millions et un PUH"
            ),
            "required_fields": ["quartier", "prix"],
            "max_age_days": 7,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["type_bien"] == "parcelle"
    assert payload["quartier"] == "Saaba"
    assert payload["superficie_m2"] == 400
    assert payload["prix_fcfa"] == 8_000_000
    assert payload["prix_est_un_maximum"] is True
    assert payload["statut_document"] == "puh"
    assert payload["contraintes_obligatoires"] == ["prix", "quartier"]


def test_interpret_rejects_too_short_description() -> None:
    response = client.post(
        "/search/interpret",
        json={"description": "a"},
    )
    assert response.status_code == 422


def test_interpret_rejects_unknown_required_field() -> None:
    response = client.post(
        "/search/interpret",
        json={
            "description": "terrain à Saaba",
            "required_fields": ["couleur"],
        },
    )
    assert response.status_code == 422
