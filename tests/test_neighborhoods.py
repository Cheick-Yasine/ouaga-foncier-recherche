"""Tests de préparation des quartiers."""

from app.neighborhoods import (
    group_variants,
    neighborhood_key,
    suggest_canonical_neighborhood,
)
from scripts.audit_neighborhoods import build_neighborhood_report


def test_case_accents_and_spacing_share_the_same_key() -> None:
    assert neighborhood_key("RIMKIETA") == neighborhood_key("Rimkiéta")
    assert neighborhood_key("OUAGA2000") == neighborhood_key("Ouaga 2000")


def test_known_aliases_return_verified_name() -> None:
    assert suggest_canonical_neighborhood("boassa") == "Boassa"
    assert suggest_canonical_neighborhood("OUAGA2000") == "Ouaga 2000"


def test_unknown_value_is_not_invented() -> None:
    assert suggest_canonical_neighborhood("Zone nouvelle inconnue") is None


def test_variant_groups_are_detected() -> None:
    groups = group_variants(
        [
            ("RIMKIETA", 10),
            ("Rimkiéta", 5),
            ("Saaba", 20),
        ]
    )

    assert len(groups["rimkieta"]) == 2
    assert len(groups["saaba"]) == 1


def test_report_is_read_only_and_counts_missing_rows() -> None:
    report = build_neighborhood_report(
        [
            (None, 2),
            ("OUAGA2000", 3),
            ("Ouaga 2000", 4),
            ("Nouvelle zone", 1),
        ]
    )

    assert report["total_rows"] == 10
    assert report["missing_rows"] == 2
    assert report["known_alias_rows"] == 7
    assert report["database_modified"] is False
    assert report["read_only"] is True
