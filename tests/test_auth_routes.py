"""Tests des routes de l'espace utilisateur."""

from fastapi.testclient import TestClient

from app.auth import AuthenticatedUser, SESSION_COOKIE
from app.main import app


client = TestClient(app)


def test_register_creates_session_cookie(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.auth_routes.create_user",
        lambda name, password: AuthenticatedUser(
            id="user-1",
            name=name.lower(),
        ),
    )
    monkeypatch.setattr(
        "app.auth_routes.create_session",
        lambda user_id: "opaque-session-token",
    )

    response = client.post(
        "/auth/register",
        json={
            "name": "Cheick Yasine",
            "password": "1234",
        },
    )

    assert response.status_code == 201
    assert response.json()["name"] == "cheick yasine"
    assert SESSION_COOKIE in response.cookies
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]


def test_login_rejects_invalid_credentials(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.auth_routes.authenticate_user",
        lambda name, password: None,
    )

    response = client.post(
        "/auth/login",
        json={
            "name": "cheick yasine",
            "password": "0000",
        },
    )

    assert response.status_code == 401


def test_me_returns_connected_user(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.auth_routes.get_session_user",
        lambda token: AuthenticatedUser(
            id="user-1",
            name="cheick yasine",
        ),
    )

    response = client.get(
        "/auth/me",
        cookies={SESSION_COOKIE: "session-token"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == "user-1"
    assert response.json()["name"] == "cheick yasine"
