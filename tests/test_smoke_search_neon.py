"""Tests du contrôle réel de recherche Neon."""

from app.search_engine import SearchCandidate
from scripts import smoke_search_neon


def test_safe_report_does_not_export_announcements(monkeypatch) -> None:
    monkeypatch.setattr(
        smoke_search_neon,
        "load_recent_candidates",
        lambda _days: [
            SearchCandidate(
                identifier="secret-post-id",
                text="Texte privé de l'annonce",
                property_type="parcelle",
                neighborhood="Ouagadougou",
                price_fcfa=5_000_000,
                area_m2=300,
                url="https://facebook.com/private",
                age_days=1,
            )
        ],
    )

    report = smoke_search_neon.build_safe_report(
        "Je cherche une parcelle à Ouagadougou"
    )
    rendered = str(report)

    assert report["statut"] == "ok"
    assert report["candidats_charges"] == 1
    assert report["resultats_classes"] == 1
    assert "secret-post-id" not in rendered
    assert "Texte privé" not in rendered
    assert "facebook.com" not in rendered
    assert "5000000" not in rendered
