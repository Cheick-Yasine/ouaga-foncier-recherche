"""Tests du référentiel géographique."""

from app.neighborhoods import (
    CANONICAL_NEIGHBORHOODS,
    group_variants,
    is_in_geographic_scope,
    neighborhood_key,
    neighborhood_metadata,
    resolve_neighborhood,
    suggest_canonical_neighborhood,
)
from scripts.audit_neighborhoods import build_neighborhood_report


def test_reference_has_no_duplicate_canonical_name() -> None:
    assert len(CANONICAL_NEIGHBORHOODS) == len(set(CANONICAL_NEIGHBORHOODS))


def test_case_accents_spacing_and_punctuation_share_keys() -> None:
    assert neighborhood_key("RIMKIETA") == neighborhood_key("Rimkièta")
    assert neighborhood_key("OUAGA2000") == neighborhood_key("Ouaga 2000")
    assert neighborhood_key("Centre-ville") == neighborhood_key("Centre Ville")


def test_confirmed_aliases_return_canonical_name() -> None:
    assert suggest_canonical_neighborhood("OUAGA2000") == "Ouaga 2000"
    assert suggest_canonical_neighborhood("Cité An III") == "Cité An 3"
    assert suggest_canonical_neighborhood("centre-ville") == "Centre Ville"


def test_potentially_distinct_places_are_not_silently_merged() -> None:
    assert suggest_canonical_neighborhood("Baossa") == "Baossa"
    assert suggest_canonical_neighborhood("Boassa") == "Boassa"
    assert suggest_canonical_neighborhood("Kamboinsé") == "Kamboinsé"
    assert suggest_canonical_neighborhood("Kamboinsin") == "Kamboinsin"


def test_specific_subzones_remain_distinct() -> None:
    assert suggest_canonical_neighborhood("Dapoya") == "Dapoya"
    assert suggest_canonical_neighborhood("Dapoya 2") == "Dapoya 2"
    assert suggest_canonical_neighborhood("Gounghin Nord") == "Gounghin Nord"
    assert suggest_canonical_neighborhood("Gounghin Sud") == "Gounghin Sud"


def test_city_is_in_scope_but_not_a_precise_neighborhood() -> None:
    metadata = neighborhood_metadata("Ouagadougou")
    assert metadata["in_scope"] is True
    assert metadata["zone_type"] == "ville"
    assert metadata["precision"] == "ville_seulement"


def test_peripheral_commune_is_classified() -> None:
    metadata = neighborhood_metadata("Koubri")
    assert metadata["in_scope"] is True
    assert metadata["zone_type"] == "commune_peripherique"
    assert metadata["precision"] == "commune"


def test_unknown_value_is_not_invented_and_is_out_of_scope() -> None:
    assert suggest_canonical_neighborhood("Bobo-Dioulasso") is None
    assert is_in_geographic_scope("Bobo-Dioulasso") is False
    assert neighborhood_metadata("Zone nouvelle inconnue")["status"] == "review_required"


def test_variant_groups_are_detected() -> None:
    groups = group_variants([("RIMKIETA", 10), ("Rimkièta", 5), ("Saaba", 20)])
    assert len(groups["rimkieta"]) == 2
    assert len(groups["saaba"]) == 1


def test_report_is_read_only_and_counts_missing_rows() -> None:
    report = build_neighborhood_report(
        [(None, 2), ("OUAGA2000", 3), ("Ouaga 2000", 4), ("Bobo", 1)]
    )
    assert report["total_rows"] == 10
    assert report["missing_rows"] == 2
    assert report["known_alias_rows"] == 7
    assert report["database_modified"] is False
    assert report["read_only"] is True


def test_sapouy_is_not_confused_with_norbert_zongo() -> None:
    resolution = resolve_neighborhood(
        "13 ha avec APFR au goudron Sapouy à côté de ferme Norbert Zongo",
        "Zongo",
    )

    assert resolution.canonical is None
    assert resolution.in_scope is False
    assert resolution.source == "hors_perimetre"


def test_actual_kamboinsin_location_precedes_route_to_yagma() -> None:
    resolution = resolve_neighborhood(
        "Parcelle à vendre au quartier Kamboinsin sur la route de Yagma",
        "Yagma",
    )

    assert resolution.canonical == "Kamboinsin"
    assert resolution.source == "texte_nettoye"


def test_hashtag_location_precedes_after_directional_landmark() -> None:
    resolution = resolve_neighborhood(
        "#Lougsi Après Boassa facilement accessible par le goudron",
        "Boassa",
    )

    assert resolution.canonical == "Lougsi"
    assert resolution.in_scope is True


def test_directional_landmark_is_not_used_as_location() -> None:
    resolution = resolve_neighborhood(
        "Parcelle disponible après Boassa facilement accessible",
        "Boassa",
    )

    assert resolution.canonical is None
    assert resolution.in_scope is False


def test_explicit_location_precedes_route_landmark_generically() -> None:
    resolution = resolve_neighborhood(
        "Terrain situé à Saaba sur la route de Koubri",
        "Koubri",
    )

    assert resolution.canonical == "Saaba"
