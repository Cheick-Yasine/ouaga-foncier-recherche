"""Règles déterministes de normalisation des annonces immobilières."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable


ALLOWED_PROPERTY_TYPES = frozenset({"terrain", "parcelle", "maison"})

_DIRECT_TYPE_MAPPING = {
    "terrain": "terrain",
    "terrains": "terrain",
    "ferme": "terrain",
    "fermes": "terrain",
    "parcelle": "parcelle",
    "parcelles": "parcelle",
    "maison": "maison",
    "maisons": "maison",
    "villa": "maison",
    "villas": "maison",
}

_TEXT_SIGNALS = {
    "maison": re.compile(
        r"\b(maison|villa|duplex|triplex|immeuble|bâtiment|batiment)\b",
        re.IGNORECASE,
    ),
    "parcelle": re.compile(r"\bparcelles?\b", re.IGNORECASE),
    "terrain": re.compile(
        r"\b(terrains?|fermes?|domaines?)\b",
        re.IGNORECASE,
    ),
}


def _simplify(value: str | None) -> str:
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    return " ".join(without_accents.casefold().split())


def _detected_types(texts: Iterable[str | None]) -> set[str]:
    searchable_text = _simplify(" ".join(text or "" for text in texts))
    return {
        property_type
        for property_type, pattern in _TEXT_SIGNALS.items()
        if pattern.search(searchable_text)
    }


def normalize_property_type(
    original_type: str | None,
    *descriptive_texts: str | None,
) -> str | None:
    """Retourne terrain, parcelle, maison ou None si le cas est ambigu.

    La valeur structurée d'origine est prioritaire. Le texte sert uniquement
    aux anciennes lignes classées « autre » ou sans type. Plusieurs familles
    de mots-clés détectées simultanément produisent None afin de ne pas inventer.
    """

    simplified_type = _simplify(original_type)
    if simplified_type in _DIRECT_TYPE_MAPPING:
        return _DIRECT_TYPE_MAPPING[simplified_type]

    detected = _detected_types(descriptive_texts)
    if len(detected) == 1:
        return detected.pop()
    return None
