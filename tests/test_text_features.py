"""Tests de l'extraction des caractéristiques textuelles."""

from datetime import datetime, timezone

from app.text_features import (
    build_text_features_audit,
    extract_document_status,
    extract_proximity,
    extract_text_features,
    extract_viability,
)


def _row(identifier: str, text: str) -> dict[str, object]:
    return {
        "id": identifier,
        "url": f"https://facebook.com/posts/{identifier}",
        "texte_nettoye": f"{text} référence {identifier}",
        "resume_court": text,
        "mots_cles_pertinents": None,
        "quartier_zone": "Saaba",
        "type_bien": "terrain",
        "type_bien_normalise": "terrain",
        "prix_fcfa": 20_000_000,
        "superficie_m2": 300,
        "statut_document": None,
        "premiere_collecte": datetime(2026, 8, 1, tzinfo=timezone.utc),
        "derniere_maj": datetime(2026, 8, 1, tzinfo=timezone.utc),
    }


def test_paved_road_is_one_proximity_not_multiple() -> None:
    assert extract_proximity("Terrain situé au bord d'une route bitumée") == "voie_bitumee"


def test_multiple_distinct_proximities() -> None:
    assert (
        extract_proximity("À côté d'une école et d'un centre de santé")
        == "plusieurs"
    )


def test_road_and_missing_proximity() -> None:
    assert extract_proximity("Proche de la route nationale") == "voie_route"
    assert extract_proximity("Très beau terrain") == "non_precisee"


def test_viability_categories() -> None:
    assert extract_viability("Zone raccordée à l'eau et à l'électricité") == "eau_et_electricite"
    assert extract_viability("Branchement ONEA disponible") == "eau"
    assert extract_viability("Zone couverte par la SONABEL") == "electricite"
    assert extract_viability("Zone calme") == "non_precisee"


def test_document_categories() -> None:
    assert extract_document_status("PUH") == "puh"
    assert extract_document_status(None, "Terrain avec titre foncier") == "titre_foncier"
    assert (
        extract_document_status(
            None,
            "Attestation de possession foncière rurale disponible",
        )
        == "apfr"
    )
    assert extract_document_status(None, "Aucun détail documentaire") == "non_precise"


def test_features_are_extracted_without_removing_rows() -> None:
    rows = [
        _row(
            "one",
            "Terrain proche d'une école, avec eau, électricité et PUH à Saaba",
        ),
        _row("two", "Terrain calme à Saaba"),
    ]
    report, trace = build_text_features_audit(rows)
    assert report["observations_avant_extraction"] == 2
    assert report["observations_supprimees_extraction"] == 0
    assert report["observations_restantes"] == 2
    assert len(trace) == 2


def test_structured_document_and_text_are_combined() -> None:
    row = _row("document", "Terrain avec accès au goudron")
    row["statut_document"] = "Attestation d'attribution"
    features = extract_text_features(row)
    assert features["proximite"] == "voie_bitumee"
    assert features["statut_document_normalise"] == "attestation_attribution"


def test_published_report_contains_only_aggregates() -> None:
    report, _ = build_text_features_audit([_row("private-id", "Terrain à Saaba")])
    assert "private-id" not in repr(report)
    assert report["identifiers_exported"] is False
    assert report["database_modified"] is False


def test_possession_is_not_confused_with_attribution() -> None:
    assert (
        extract_document_status(
            None,
            "Attestation de possession disponible.",
        )
        == "attestation_possession"
    )
    assert (
        extract_document_status(
            None,
            "Fiche d'attribution disponible.",
        )
        == "attestation_attribution"
    )


def test_explicit_ad_text_overrides_stale_structured_document() -> None:
    assert (
        extract_document_status(
            "attestation_attribution",
            "Attestation de possession disponible.",
        )
        == "attestation_possession"
    )


def test_paved_proximity_and_paved_access_are_distinct() -> None:
    assert (
        extract_proximity("Parcelle proche d'une voie bitumée")
        == "voie_bitumee"
    )
    assert (
        extract_proximity("Parcelle facilement accessible par le goudron")
        == "acces_voie_bitumee"
    )


def test_directional_landmark_does_not_imply_paved_proximity() -> None:
    assert (
        extract_proximity("Après Boassa facilement accessible par le goudron")
        == "acces_voie_bitumee"
    )
