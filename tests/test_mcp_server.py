"""Tests des outils publics du serveur MCP."""

from app import mcp_server
from app.public_references import public_announcement_id
from app.search_engine import SearchCandidate
from app.semantic_filter import SemanticFilterOutcome


def test_interpreter_recherche_returns_structured_criteria() -> None:
    result = mcp_server.interpreter_recherche(
        "Je cherche une parcelle à Saaba de 300 m2 à 5 millions avec PUH"
    )

    assert result["type_bien"] == "parcelle"
    assert result["quartier"] == "Saaba"
    assert result["prix_fcfa"] == 5_000_000
    assert result["superficie_m2"] == 300
    assert result["document"] == "puh"


def test_search_never_returns_contact(monkeypatch) -> None:
    candidate = SearchCandidate(
        identifier="post-1",
        text="Parcelle de 300 m2 à Saaba avec PUH. Contact 70 12 34 56",
        property_type="parcelle",
        neighborhood="Saaba",
        price_fcfa=5_000_000,
        area_m2=300,
        document_status="puh",
        url="https://facebook.com/posts/1",
        contact="70 12 34 56",
    )
    periods = []

    def load_candidates(max_age_days):
        periods.append(max_age_days)
        return [candidate]

    monkeypatch.setattr(
        mcp_server,
        "load_recent_candidates",
        load_candidates,
    )

    def keep_local(_criteria, ranked, *, settings):
        return SemanticFilterOutcome(ranked, False, None, True)

    monkeypatch.setattr(mcp_server, "apply_semantic_filter", keep_local)

    response = mcp_server.rechercher_annonces(
        "Parcelle à Saaba de 300 m2, 5 millions, PUH"
    )
    rendered = str(response)

    assert response["nombre_resultats"] == 1
    assert periods == [30]
    assert response["criteres"]["anciennete_maximale_jours"] == 30
    assert response["results"][0]["id"] != "post-1"
    assert response["results"][0]["prix_m2_fcfa"] == 16_666.67
    assert response["results"][0]["url"].startswith("https://ouaga-foncier-mcp.onrender.com/?annonce=")
    assert "facebook.com" not in response["results"][0]["url"]
    assert "contact" not in response["results"][0]
    assert "70 12 34 56" not in response["results"][0]["description"]
    assert "[contact retire]" in response["results"][0]["description"]


def test_fetch_excludes_source_identity_link_and_contact(monkeypatch) -> None:
    candidate = SearchCandidate(
        identifier="post-2",
        text="Terrain à Karpala. Contact 76 00 00 00",
        property_type="terrain",
        neighborhood="Karpala",
        url="https://facebook.com/posts/2",
        contact="76 00 00 00",
    )
    monkeypatch.setattr(
        mcp_server,
        "load_recent_candidates",
        lambda _max_age: [candidate],
    )

    public_id = public_announcement_id(candidate.identifier)
    response = mcp_server.fetch(public_id)
    rendered = str(response)

    assert response["id"] == public_id
    assert response["id"] != "post-2"
    assert response["url"] is None
    assert "facebook.com" not in rendered
    assert "contact" not in response
    assert "76 00 00 00" not in rendered

def test_unsupported_period_is_rejected() -> None:
    response = mcp_server.rechercher_annonces(
        "Terrain à Saaba",
        anciennete_jours=14,
    )

    assert response["erreur"] == "La période doit être de 7, 30 ou 90 jours."


def test_unknown_required_criterion_is_rejected() -> None:
    response = mcp_server.rechercher_annonces(
        "Terrain à Saaba",
        criteres_obligatoires=["couleur"],
    )
    assert "erreur" in response
    assert "couleur" in response["erreur"]


def test_search_alias_uses_compatibility_results(monkeypatch) -> None:
    monkeypatch.setattr(
        mcp_server,
        "rechercher_annonces",
        lambda query, limit=10: {
            "results": [{"id": "1", "title": query, "url": None}]
        },
    )
    response = mcp_server.search("terrain à Saaba")
    assert response["results"][0]["title"] == "terrain à Saaba"
