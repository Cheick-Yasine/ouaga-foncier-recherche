"""Tests de la consultation protégée des annonces."""

from fastapi.testclient import TestClient

from app.auth import AuthenticatedUser
from app.main import app
from app.public_references import public_announcement_id
from app.search_engine import SearchCandidate


client = TestClient(app)


def test_announcement_requires_authentication(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.announcement_routes.get_session_user",
        lambda _token: None,
    )

    response = client.get("/annonces/reference")
    assert response.status_code == 401
    assert response.json()["detail"] == "Connexion requise."


def test_authenticated_user_can_view_contact_and_source(monkeypatch) -> None:
    candidate = SearchCandidate(
        identifier="post-secret",
        text="Parcelle à Saaba de 300 m2",
        property_type="parcelle",
        neighborhood="Saaba",
        price_fcfa=4_000_000,
        area_m2=300,
        document_status="attestation",
        url="https://facebook.com/posts/secret",
        contact="70 12 34 56",
    )
    monkeypatch.setattr(
        "app.announcement_routes.get_session_user",
        lambda _token: AuthenticatedUser(id="user-1", email="client@example.com"),
    )
    monkeypatch.setattr(
        "app.announcement_routes.load_recent_candidates",
        lambda _days: [candidate],
    )

    reference = public_announcement_id(candidate.identifier)
    response = client.get(
        f"/annonces/{reference}",
        cookies={"of_session": "token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == reference
    assert payload["contact"] == "70 12 34 56"
    assert payload["lien_whatsapp"] == "https://wa.me/22670123456"
    assert payload["url"] == "https://facebook.com/posts/secret"
    assert "post-secret" not in response.text
