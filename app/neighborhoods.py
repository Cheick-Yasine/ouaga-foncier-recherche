"""Outils déterministes pour préparer la normalisation des quartiers."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable


KNOWN_NEIGHBORHOOD_ALIASES = {
    "ouaga 2000": "Ouaga 2000",
    "ouaga2000": "Ouaga 2000",
    "ouagadougou 2000": "Ouaga 2000",
    "rimkieta": "Rimkiéta",
    "boassa": "Boassa",
    "saaba": "Saaba",
    "karpala": "Karpala",
    "zagtouli": "Zagtouli",
    "bassinko": "Bassinko",
    "koubri": "Koubri",
    "tanghin": "Tanghin",
    "tampouy": "Tampouy",
    "kamboinsin": "Kamboinsin",
    "yagma": "Yagma",
    "kouba": "Kouba",
    "bonheur ville": "Bonheur Ville",
    "komsilga": "Komsilga",
    "loumbila": "Loumbila",
    "kossodo": "Kossodo",
    "nagrin": "Nagrin",
}

_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")
_SPACE_BETWEEN_TEXT_AND_NUMBER = re.compile(r"(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])")


def neighborhood_key(value: str | None) -> str:
    """Construit une clé comparable sans inventer de quartier."""

    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    simplified = without_accents.casefold().strip()
    simplified = _SPACE_BETWEEN_TEXT_AND_NUMBER.sub(" ", simplified)
    simplified = _NON_ALPHANUMERIC.sub(" ", simplified)
    return " ".join(simplified.split())


def suggest_canonical_neighborhood(value: str | None) -> str | None:
    """Retourne uniquement une correspondance connue et vérifiée."""

    key = neighborhood_key(value)
    return KNOWN_NEIGHBORHOOD_ALIASES.get(key)


def group_variants(values: Iterable[tuple[str, int]]) -> dict[str, list[tuple[str, int]]]:
    """Regroupe les graphies équivalentes par casse, accents et ponctuation."""

    groups: dict[str, list[tuple[str, int]]] = {}
    for raw_value, count in values:
        key = neighborhood_key(raw_value)
        if not key:
            continue
        groups.setdefault(key, []).append((raw_value, count))
    return groups
