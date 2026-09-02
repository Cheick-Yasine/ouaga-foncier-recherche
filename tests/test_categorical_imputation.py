"""Tests de l'imputation catégorielle."""

from datetime import datetime, timedelta, timezone

from app.categorical_imputation import (
    MISSING_CATEGORY,
    build_categorical_imputation_audit,
    impute_category,
)


def _row(
    identifier: str,
    *,
    property_type: str | None,
    text: str,
    day: int,
) -> dict[str, object]:
    return {
        "id": identifier,
        "url": f"https://facebook.com/posts/{identifier}",
        "texte_nettoye": f"{text} référence {identifier}",
        "resume_court": text,
        "mots_cles_pertinents": None,
        "quartier_zone": "Saaba",
        "type_bien": property_type,
        "type_bien_normalise": None,
        "prix_fcfa": 20_000_000,
        "superficie_m2": 300,
        "statut_document": None,
        "premiere_collecte": datetime(2026, 8, 1, tzinfo=timezone.utc)
        + timedelta(days=day),
        "derniere_maj": datetime(2026, 8, 1, tzinfo=timezone.utc)
        + timedelta(days=day),
    }


def test_only_null_empty_or_spaces_become_missing() -> None:
    assert impute_category(None) == MISSING_CATEGORY
    assert impute_category("") == MISSING_CATEGORY
    assert impute_category("   ") == MISSING_CATEGORY
    assert impute_category("terrain") == "terrain"


def test_non_precisee_is_not_rewritten_as_missing() -> None:
    assert impute_category("non_precisee") == "non_precisee"
    assert impute_category("non_precise") == "non_precise"


def test_ambiguous_type_becomes_missing_without_removing_row() -> None:
    rows = [
        _row(
            "known",
            property_type="terrain",
            text="Terrain calme à Saaba",
            day=0,
        ),
        _row(
            "unknown",
            property_type="autre",
            text="Bien immobilier calme à Saaba",
            day=1,
        ),
    ]
    report, trace = build_categorical_imputation_audit(rows)

    assert report["observations_restantes"] == 2
    assert report["observations_supprimees_imputation_categorielle"] == 0
    assert (
        report["valeurs_converties_en_manquante"]["type_bien_normalise"]
        == 1
    )

    by_id = {item["id"]: item for item in trace}
    assert by_id["known"]["type_bien_normalise"] == "terrain"
    assert by_id["unknown"]["type_bien_normalise"] == MISSING_CATEGORY
    assert by_id["unknown"]["proximite"] == "non_precisee"
    assert by_id["unknown"]["viabilite"] == "non_precisee"
    assert by_id["unknown"]["statut_document"] == "non_precise"


def test_all_final_categories_are_non_empty() -> None:
    _, trace = build_categorical_imputation_audit(
        [
            _row(
                "unknown",
                property_type=None,
                text="Bien immobilier à Saaba",
                day=0,
            )
        ]
    )
    fields = (
        "quartier_final",
        "type_bien_normalise",
        "proximite",
        "viabilite",
        "statut_document",
    )
    assert all(trace[0][field].strip() for field in fields)


def test_published_report_contains_only_aggregates() -> None:
    report, _ = build_categorical_imputation_audit(
        [
            _row(
                "private-id",
                property_type="parcelle",
                text="Parcelle à Saaba",
                day=0,
            )
        ]
    )
    assert "private-id" not in repr(report)
    assert report["identifiers_exported"] is False
    assert report["database_modified"] is False
