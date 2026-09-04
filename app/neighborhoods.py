"""Référentiel déterministe des zones retenues pour Ouaga Foncier."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import asdict, dataclass


# Noms métier validés. Les doublons orthographiques sont gérés par les alias.
CANONICAL_NEIGHBORHOODS = (
    "Bilbalogo", "Saint Léon", "Zangouettin", "Tiedpalogo", "Koulouba",
    "Sabtenga", "Gampela", "Kamsonghin", "Samandin", "Gounghin Sud",
    "Gandin", "Kouritenga", "Mankougoudou", "Paspanga", "Ouidi", "Larlé",
    "Kologh Naba", "Dapoya", "Dapoya 2", "Nemnin", "Niogsin", "Hamdalaye",
    "Gounghin Nord", "Baoghin", "Camp Militaire", "Sabtoana", "Baossa",
    "Naababpougo", "Kienbaoghin", "Zongo", "Koumdayonré", "Nonsin",
    "Rimkièta", "Kouba", "Sonré", "Tampouy", "Kilwin", "Tanghin", "Sambin",
    "Somgandé", "Zone Industrielle", "Nioko 2", "Bendogo", "Toukin", "Zogona",
    "Wemtenga", "Dagnoën", "Ronsin", "Kalgondin", "Pissy", "Kwaré",
    "Pacsnoma", "Yagma", "Silmiougou", "Wayalghin", "Kossodo", "Polesgo",
    "Dassasgho", "Nagrin", "Nongr-Massom", "Cissin", "Yamtenga", "Balkuy",
    "Kamboinsé", "Ouaga 2000", "Goughin", "Zone du Bois", "Patte d'Oie",
    "Bassinko", "Loumbila", "Saaba", "Zagtouli", "Kamboinsin", "Boassa",
    "Sandogo", "Tengandogo", "Sig-Noghin", "Bissighin", "Darsalam",
    "Cité Bancaire", "Cité An 3", "Cité Socogib", "Cité Militaire",
    "Cité Abbé Simard", "Cité Bonheur", "Cité Azimo", "Cité Railtel",
    "Cité Bolesse", "Zone Commerciale", "Centre Ville", "Paglayiri",
    "Bilibambili", "Mogho Naaba", "Kuinima", "Bindougousso", "Zéca", "Baskuy",
    "Pabré", "Koubri", "Komsilga", "Ouagadougou", "Karpala",
)

PERIPHERAL_COMMUNES = frozenset({"Loumbila", "Saaba", "Pabré", "Koubri", "Komsilga"})
ADMINISTRATIVE_AREAS = frozenset({"Baskuy", "Nongr-Massom"})
BROAD_AREAS = frozenset({"Centre Ville", "Zone Industrielle", "Zone Commerciale"})
CITY_LEVEL_AREAS = frozenset({"Ouagadougou"})

# Localités explicitement hors du périmètre validé Ouagadougou + périphérie.
# Leur présence comme lieu principal invalide les faux quartiers homonymes
# rencontrés dans des noms de personnes ou de structures (ex. Norbert Zongo).
OUT_OF_SCOPE_LOCALITIES = (
    "Bobo-Dioulasso", "Koudougou", "Sapouy", "Tenkodogo", "Ouahigouya",
    "Fada N'Gourma", "Koupéla", "Manga", "Réo", "Kindi", "Kokologho",
    "Saponé", "Ziniaré", "Dédougou", "Banfora", "Kaya", "Dori",
)

_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")
_SPACE_BETWEEN_TEXT_AND_NUMBER = re.compile(r"(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])")


def neighborhood_key(value: str | None) -> str:
    """Construit une clé comparable sans accents, casse ni ponctuation."""

    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    simplified = without_accents.casefold().strip()
    simplified = _SPACE_BETWEEN_TEXT_AND_NUMBER.sub(" ", simplified)
    simplified = _NON_ALPHANUMERIC.sub(" ", simplified)
    return " ".join(simplified.split())


_CANONICAL_BY_KEY = {
    neighborhood_key(neighborhood): neighborhood
    for neighborhood in CANONICAL_NEIGHBORHOODS
}

# Variantes confirmées qui ne sont pas déjà réunies par neighborhood_key().
KNOWN_NEIGHBORHOOD_ALIASES = {
    **_CANONICAL_BY_KEY,
    "ouagadougou 2000": "Ouaga 2000",
    "cite an iii": "Cité An 3",
}


@dataclass(frozen=True)
class NeighborhoodMetadata:
    original: str | None
    comparison_key: str
    canonical: str | None
    in_scope: bool
    zone_type: str | None
    precision: str
    status: str


@dataclass(frozen=True)
class NeighborhoodResolution:
    canonical: str | None
    source: str
    detected_candidates: tuple[str, ...]
    in_scope: bool
    zone_type: str | None
    precision: str


def suggest_canonical_neighborhood(value: str | None) -> str | None:
    """Retourne une zone canonique uniquement lorsqu'elle appartient au référentiel."""

    return KNOWN_NEIGHBORHOOD_ALIASES.get(neighborhood_key(value))


def neighborhood_metadata(value: str | None) -> dict[str, object]:
    """Décrit la normalisation et la précision géographique d'une valeur."""

    key = neighborhood_key(value)
    canonical = KNOWN_NEIGHBORHOOD_ALIASES.get(key)
    if canonical in PERIPHERAL_COMMUNES:
        zone_type, precision = "commune_peripherique", "commune"
    elif canonical in ADMINISTRATIVE_AREAS:
        zone_type, precision = "zone_administrative", "large"
    elif canonical in BROAD_AREAS:
        zone_type, precision = "zone_large", "large"
    elif canonical in CITY_LEVEL_AREAS:
        zone_type, precision = "ville", "ville_seulement"
    elif canonical:
        zone_type, precision = "quartier", "quartier"
    else:
        zone_type, precision = None, "inconnue"

    metadata = NeighborhoodMetadata(
        original=value,
        comparison_key=key,
        canonical=canonical,
        in_scope=canonical is not None,
        zone_type=zone_type,
        precision=precision,
        status="reference" if canonical else "review_required",
    )
    return asdict(metadata)


def is_in_geographic_scope(value: str | None) -> bool:
    """Indique si une valeur appartient à la liste géographique autorisée."""

    return suggest_canonical_neighborhood(value) is not None


def detect_neighborhoods(text: str | None) -> tuple[str, ...]:
    """Détecte les zones du référentiel en privilégiant les noms les plus précis."""

    searchable = neighborhood_key(text)
    if not searchable:
        return ()

    raw_matches: list[tuple[int, int, str]] = []
    for alias, canonical in KNOWN_NEIGHBORHOOD_ALIASES.items():
        pattern = re.compile(
            rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])"
        )
        raw_matches.extend(
            (match.start(), match.end(), canonical)
            for match in pattern.finditer(searchable)
        )

    # « Dapoya 2 » doit gagner sur « Dapoya » lorsqu'ils couvrent le même passage.
    selected: list[tuple[int, int, str]] = []
    for candidate in sorted(
        raw_matches,
        key=lambda item: (-(item[1] - item[0]), item[0], item[2]),
    ):
        start, end, _ = candidate
        if any(start < chosen_end and end > chosen_start for chosen_start, chosen_end, _ in selected):
            continue
        selected.append(candidate)

    ordered: list[str] = []
    for _, _, canonical in sorted(selected, key=lambda item: item[0]):
        if canonical not in ordered:
            ordered.append(canonical)
    return tuple(ordered)


def detect_explicit_neighborhood(text: str | None) -> str | None:
    """Détecte le lieu principal à partir de formulations géographiques fortes."""

    searchable = neighborhood_key(text)
    if not searchable:
        return None

    priority_prefixes = (
        r"(?:localisation|quartier|secteur|village)\s*(?::|-)?\s*",
        r"(?:situee?|localisee?|se trouve|est)\s+a\s+",
        r"\ba\s+",
    )
    aliases = sorted(
        KNOWN_NEIGHBORHOOD_ALIASES.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    for prefix in priority_prefixes:
        matches: list[tuple[int, str]] = []
        for alias, canonical in aliases:
            pattern = re.compile(
                rf"{prefix}{re.escape(alias)}(?![a-z0-9])"
            )
            matches.extend(
                (match.start(), canonical)
                for match in pattern.finditer(searchable)
            )
        if matches:
            return min(matches, key=lambda item: item[0])[1]
    return None


def detect_out_of_scope_locality(text: str | None) -> str | None:
    """Repère une localisation principale connue hors du périmètre autorisé."""

    searchable = neighborhood_key(text)
    for locality in OUT_OF_SCOPE_LOCALITIES:
        key = neighborhood_key(locality)
        if re.search(
            rf"(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])",
            searchable,
        ):
            return locality
    return None


def resolve_neighborhood(
    text: str | None,
    fallback: str | None,
) -> NeighborhoodResolution:
    """Résout le quartier depuis le texte, puis depuis quartier_zone en repli."""

    candidates = detect_neighborhoods(text)
    fallback_canonical = suggest_canonical_neighborhood(fallback)
    explicit = detect_explicit_neighborhood(text)
    outside = detect_out_of_scope_locality(text)

    if outside:
        canonical = None
        source = "hors_perimetre"
    elif explicit:
        canonical = explicit
        source = "texte_nettoye"
    elif len(candidates) == 1:
        canonical = candidates[0]
        source = "texte_nettoye"
    elif fallback_canonical:
        canonical = fallback_canonical
        source = "quartier_zone"
    else:
        canonical = None
        source = "non_resolu_multiple" if len(candidates) > 1 else "non_resolu"

    metadata = neighborhood_metadata(canonical)
    return NeighborhoodResolution(
        canonical=canonical,
        source=source,
        detected_candidates=candidates,
        in_scope=canonical is not None,
        zone_type=metadata["zone_type"],
        precision=str(metadata["precision"]),
    )


def group_variants(values: Iterable[tuple[str, int]]) -> dict[str, list[tuple[str, int]]]:
    """Regroupe les graphies équivalentes par casse, accents et ponctuation."""

    groups: dict[str, list[tuple[str, int]]] = {}
    for raw_value, count in values:
        key = neighborhood_key(raw_value)
        if key:
            groups.setdefault(key, []).append((raw_value, count))
    return groups
