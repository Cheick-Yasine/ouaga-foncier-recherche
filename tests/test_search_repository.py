"""Tests de la lecture Neon des candidats."""

from datetime import datetime, timedelta, timezone

from app.search_repository import _candidate_from_row


def test_row_is_mapped_to_search_candidate() -> None:
    now = datetime(2026, 9, 3, 12, tzinfo=timezone.utc)
    candidate = _candidate_from_row(
        {
            "id": "post-1",
            "url": "https://facebook.com/posts/1",
            "date_publication": "Il y a 2 heures",
            "type_bien": "Parcelle",
            "type_bien_normalise": "parcelle",
            "quartier_zone": "Saaba",
            "superficie_m2": 300,
            "prix_fcfa": 5_000_000,
            "statut_document": "PUH",
            "resume_court": None,
            "texte_nettoye": (
                "Parcelle de 300 m2 à Saaba avec eau et PUH"
            ),
            "premiere_collecte": now - timedelta(days=2),
        },
        now=now,
    )

    assert candidate.identifier == "post-1"
    assert candidate.property_type == "parcelle"
    assert candidate.neighborhood == "Saaba"
    assert candidate.price_fcfa == 5_000_000
    assert candidate.area_m2 == 300
    assert candidate.viability == "eau"
    assert candidate.document_status == "puh"
    assert candidate.age_days == 2
    assert candidate.publication_label == "Il y a 2 heures"
    assert candidate.collected_at == "2026-09-01T12:00:00+00:00"


def test_missing_numeric_value_is_preserved() -> None:
    now = datetime(2026, 9, 3, 12, tzinfo=timezone.utc)
    candidate = _candidate_from_row(
        {
            "id": "post-2",
            "url": None,
            "date_publication": None,
            "type_bien": "Terrain",
            "type_bien_normalise": "terrain",
            "quartier_zone": "Karpala",
            "superficie_m2": 400,
            "prix_fcfa": None,
            "statut_document": None,
            "resume_court": "Terrain à Karpala",
            "texte_nettoye": None,
            "premiere_collecte": now,
        },
        now=now,
    )

    assert candidate.price_fcfa is None
    assert candidate.area_m2 == 400
    assert candidate.text == "Terrain à Karpala"
