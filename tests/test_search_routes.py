"""Tests des routes de recherche."""

import time

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


def test_interpret_uses_one_month_by_default() -> None:
    response = client.post(
        "/search/interpret",
        json={"description": "terrain à Saaba"},
    )

    assert response.status_code == 200
    assert response.json()["anciennete_maximale_jours"] == 30


def test_interpret_rejects_unsupported_period() -> None:
    response = client.post(
        "/search/interpret",
        json={"description": "terrain à Saaba", "max_age_days": 14},
    )

    assert response.status_code == 422


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


def test_search_returns_ranked_neon_candidates(monkeypatch) -> None:
    from app.search_engine import SearchCandidate

    monkeypatch.setattr(
        "app.search_routes.load_recent_candidates",
        lambda max_age_days: [
            SearchCandidate(
                identifier="post-1",
                text="Parcelle à Saaba de 300 m2 avec PUH",
                property_type="parcelle",
                neighborhood="Saaba",
                price_fcfa=5_000_000,
                area_m2=300,
                document_status="puh",
                age_days=1,
                url="https://facebook.com/posts/1",
                publication_label="Il y a une heure",
                collected_at="2026-09-03T10:00:00+00:00",
            ),
            SearchCandidate(
                identifier="post-2",
                text="Terrain à Karpala",
                property_type="terrain",
                neighborhood="Karpala",
                price_fcfa=4_000_000,
                area_m2=600,
                age_days=2,
            ),
        ],
    )

    response = client.post(
        "/search",
        json={
            "description": (
                "Parcelle à Saaba de 300 m², budget maximum 5 millions, PUH"
            ),
            "max_age_days": 7,
            "limit": 10,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["candidats_evalues"] == 2
    assert payload["nombre_resultats"] == 2
    assert payload["resultats"][0]["id"] == "post-1"
    assert payload["resultats"][0]["date_publication"] == "Il y a une heure"
    assert payload["resultats"][0]["score"] > payload["resultats"][1]["score"]


def test_search_reports_missing_database(monkeypatch) -> None:
    from app.database import DatabaseNotConfiguredError

    def fail(_max_age_days: int):
        raise DatabaseNotConfiguredError("DATABASE_URL absente")

    monkeypatch.setattr("app.search_routes.load_recent_candidates", fail)
    response = client.post(
        "/search",
        json={"description": "terrain à Saaba"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "DATABASE_URL absente"


def test_contact_is_masked_for_visitor(monkeypatch) -> None:
    from app.search_engine import SearchCandidate

    monkeypatch.setattr(
        "app.search_routes.load_recent_candidates",
        lambda _days: [
            SearchCandidate(
                identifier="post-contact",
                text="Parcelle à Saaba",
                contact="70 12 34 56",
            )
        ],
    )
    monkeypatch.setattr(
        "app.search_routes.get_session_user",
        lambda _token: None,
    )

    response = client.post(
        "/search",
        json={"description": "parcelle à Saaba"},
    )
    result = response.json()["resultats"][0]

    assert result["contact"] is None
    assert result["contact_masque"] == "70 ** ** 56"
    assert result["lien_whatsapp"] is None
    assert result["connexion_requise_pour_contact"] is True


def test_contact_is_visible_for_authenticated_user(monkeypatch) -> None:
    from app.auth import AuthenticatedUser
    from app.search_engine import SearchCandidate

    monkeypatch.setattr(
        "app.search_routes.load_recent_candidates",
        lambda _days: [
            SearchCandidate(
                identifier="post-contact",
                text="Parcelle à Saaba",
                contact="70 12 34 56",
            )
        ],
    )
    monkeypatch.setattr(
        "app.search_routes.get_session_user",
        lambda _token: AuthenticatedUser(
            id="user-1",
            email="client@example.com",
        ),
    )

    response = client.post(
        "/search",
        json={"description": "parcelle à Saaba"},
        cookies={"of_session": "token"},
    )
    result = response.json()["resultats"][0]

    assert result["contact"] == "70 12 34 56"
    assert result["lien_whatsapp"] == "https://wa.me/22670123456"
    assert result["connexion_requise_pour_contact"] is False


def test_search_reports_neon_timeout_without_waiting_for_openai(
    monkeypatch,
) -> None:
    from app.config import Settings

    def slow_load(_max_age_days: int):
        time.sleep(0.2)
        return []

    monkeypatch.setattr("app.search_routes.load_recent_candidates", slow_load)
    monkeypatch.setattr(
        "app.search_routes.get_settings",
        lambda: Settings(database_deadline_seconds=0.05),
    )

    response = client.post(
        "/search",
        json={"description": "terrain à Saaba"},
    )

    assert response.status_code == 503
    assert "Neon met trop de temps" in response.json()["detail"]


def test_search_returns_local_results_when_semantic_filter_times_out(
    monkeypatch,
) -> None:
    from app.config import Settings
    from app.search_engine import SearchCandidate
    from app.semantic_filter import SemanticFilterOutcome

    candidate = SearchCandidate(
        identifier="local-fallback",
        text="Parcelle à Saaba de 300 m2",
        property_type="parcelle",
        neighborhood="Saaba",
        price_fcfa=5_000_000,
        area_m2=300,
    )
    monkeypatch.setattr(
        "app.search_routes.load_recent_candidates",
        lambda _days: [candidate],
    )
    monkeypatch.setattr(
        "app.search_routes.get_settings",
        lambda: Settings(llm_deadline_seconds=0.05),
    )

    def slow_filter(_criteria, results, **_kwargs):
        time.sleep(0.2)
        return SemanticFilterOutcome(
            results=[],
            used=True,
            model="gpt-4o-mini",
            fallback=False,
        )

    monkeypatch.setattr(
        "app.search_routes.apply_semantic_filter",
        slow_filter,
    )

    response = client.post(
        "/search",
        json={"description": "parcelle à Saaba"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["repli_classement_local"] is True
    assert payload["filtre_semantique_utilise"] is False
    assert payload["resultats"][0]["id"] == "local-fallback"
