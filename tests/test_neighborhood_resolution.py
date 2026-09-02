"""Tests ciblés de résolution des quartiers dans le texte."""

from app.neighborhoods import detect_neighborhoods, resolve_neighborhood


def test_longest_area_name_wins_on_same_text_span() -> None:
    assert detect_neighborhoods("Terrain à Dapoya 2") == ("Dapoya 2",)


def test_distinct_areas_are_all_reported() -> None:
    assert detect_neighborhoods("De Saaba vers Karpala") == ("Saaba", "Karpala")


def test_words_containing_an_area_name_do_not_match() -> None:
    assert detect_neighborhoods("Une personne insaabable") == ()


def test_multiple_matches_without_valid_fallback_are_unresolved() -> None:
    result = resolve_neighborhood("Entre Saaba et Karpala", "Bobo-Dioulasso")
    assert result.canonical is None
    assert result.source == "non_resolu_multiple"
    assert result.in_scope is False


def test_ouagadougou_is_scope_information_not_precise_neighborhood() -> None:
    result = resolve_neighborhood("Disponible à Ouagadougou", None)
    assert result.canonical == "Ouagadougou"
    assert result.precision == "ville_seulement"
