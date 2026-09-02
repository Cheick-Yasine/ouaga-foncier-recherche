"""Tests des catégories terrain, parcelle et maison."""

import pytest

from app.normalization import (
    ALLOWED_PROPERTY_TYPES,
    normalize_property_type,
)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("terrain", "terrain"),
        ("Terrains", "terrain"),
        ("ferme", "terrain"),
        ("PARCELLE", "parcelle"),
        ("parcelles", "parcelle"),
        ("maison", "maison"),
    ],
)
def test_direct_mapping(source: str, expected: str) -> None:
    assert normalize_property_type(source) == expected
    assert expected in ALLOWED_PROPERTY_TYPES


@pytest.mark.parametrize("source", ["villa", "Villa", "VILLAS"])
def test_villa_is_excluded(source: str) -> None:
    assert normalize_property_type(source) is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Très belle parcelle disponible à Saaba", "parcelle"),
        ("Vente d'un terrain à Koubri", "terrain"),
        ("Maison disponible à Ouaga 2000", "maison"),
    ],
)
def test_other_is_inferred_only_when_text_is_clear(
    text: str,
    expected: str,
) -> None:
    assert normalize_property_type("autre", text) == expected


def test_villa_mentioned_in_other_is_excluded() -> None:
    assert (
        normalize_property_type(
            "autre",
            "Villa disponible sur une parcelle à Ouaga 2000",
        )
        is None
    )


def test_ambiguous_text_is_not_forced() -> None:
    assert (
        normalize_property_type(
            "autre",
            "Maison construite sur une parcelle à vendre",
        )
        is None
    )


def test_unknown_text_is_not_forced() -> None:
    assert normalize_property_type("autre", "Bonne opportunité") is None
