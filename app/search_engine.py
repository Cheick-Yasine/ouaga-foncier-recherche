"""Moteur de recherche hybride : texte, critères métier et contraintes."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.neighborhoods import resolve_neighborhood
from app.normalization import normalize_property_type
from app.text_features import (
    extract_document_status,
    extract_proximity,
    extract_viability,
    normalize_text,
)


DEFAULT_WEIGHTS = {
    "texte": 0.35,
    "quartier": 0.20,
    "prix": 0.15,
    "superficie": 0.15,
    "type_bien": 0.08,
    "statut_document": 0.03,
    "proximite": 0.02,
    "viabilite": 0.02,
}

_AREA_PATTERN = re.compile(
    r"\b(\d+(?:[.,]\d+)?)\s*(?:m2|metres? carres?)\b"
)
_PRICE_PATTERN = re.compile(
    r"\b(\d[\d ]*(?:[.,]\d+)?)\s*"
    r"(milliards?|millions?|fcfa|f cfa|cfa)\b"
)


@dataclass(frozen=True)
class SearchCriteria:
    description: str
    property_type: str | None = None
    neighborhood: str | None = None
    price_fcfa: float | None = None
    price_is_maximum: bool = False
    area_m2: float | None = None
    proximity: str | None = None
    viability: str | None = None
    document_status: str | None = None
    required_fields: frozenset[str] = field(default_factory=frozenset)
    max_age_days: int = 7


@dataclass(frozen=True)
class SearchCandidate:
    identifier: str
    text: str
    property_type: str | None = None
    neighborhood: str | None = None
    price_fcfa: float | None = None
    area_m2: float | None = None
    proximity: str | None = None
    viability: str | None = None
    document_status: str | None = None
    age_days: float | None = None
    url: str | None = None


@dataclass(frozen=True)
class RankedResult:
    candidate: SearchCandidate
    score: float
    coverage: float
    components: Mapping[str, float | None]
    explanations: tuple[str, ...]


def _parse_number(value: str) -> float:
    compact = value.replace(" ", "").replace(",", ".")
    return float(compact)


def parse_search_description(description: str) -> SearchCriteria:
    """Interprète les critères explicites d'une description utilisateur."""

    normalized = normalize_text(description)
    area_match = _AREA_PATTERN.search(normalized)
    area = _parse_number(area_match.group(1)) if area_match else None

    text_without_area = _AREA_PATTERN.sub(" ", normalized)
    price_match = _PRICE_PATTERN.search(text_without_area)
    price: float | None = None
    if price_match:
        price = _parse_number(price_match.group(1))
        unit = price_match.group(2)
        if unit.startswith("million"):
            price *= 1_000_000
        elif unit.startswith("milliard"):
            price *= 1_000_000_000

    property_type = normalize_property_type(None, description)
    resolution = resolve_neighborhood(description, None)
    neighborhood = resolution.canonical if resolution.in_scope else None

    proximity = extract_proximity(description)
    viability = extract_viability(description)
    document = extract_document_status(None, description)

    maximum_markers = (
        "budget",
        "maximum",
        "max ",
        "au plus",
        "ne pas depasser",
        "ne depasse pas",
        "jusqu a",
    )
    price_is_maximum = price is not None and any(
        marker in normalized for marker in maximum_markers
    )

    return SearchCriteria(
        description=description.strip(),
        property_type=property_type,
        neighborhood=neighborhood,
        price_fcfa=price,
        price_is_maximum=price_is_maximum,
        area_m2=area,
        proximity=None if proximity == "non_precisee" else proximity,
        viability=None if viability == "non_precisee" else viability,
        document_status=None if document == "non_precise" else document,
    )


def _tokens(text: str) -> Counter[str]:
    words = normalize_text(text).split()
    terms = list(words)
    terms.extend(
        f"{words[index]}_{words[index + 1]}"
        for index in range(len(words) - 1)
    )
    return Counter(terms)


def cosine_similarity(left: str, right: str) -> float:
    """Cosinus sur fréquences de mots et bigrammes normalisés."""

    left_vector = _tokens(left)
    right_vector = _tokens(right)
    if not left_vector or not right_vector:
        return 0.0
    common = left_vector.keys() & right_vector.keys()
    numerator = sum(left_vector[key] * right_vector[key] for key in common)
    left_norm = math.sqrt(sum(value * value for value in left_vector.values()))
    right_norm = math.sqrt(sum(value * value for value in right_vector.values()))
    return numerator / (left_norm * right_norm)


def numeric_similarity(expected: float, observed: float) -> float:
    """Score symétrique dans [0, 1], égal au rapport min/max."""

    if expected <= 0 or observed <= 0:
        return 0.0
    return min(expected, observed) / max(expected, observed)


def _normalized_equal(left: str | None, right: str | None) -> bool:
    return bool(left and right and normalize_text(left) == normalize_text(right))


def _requested_components(criteria: SearchCriteria) -> list[str]:
    requested = ["texte"]
    if criteria.neighborhood:
        requested.append("quartier")
    if criteria.price_fcfa is not None:
        requested.append("prix")
    if criteria.area_m2 is not None:
        requested.append("superficie")
    if criteria.property_type:
        requested.append("type_bien")
    if criteria.document_status:
        requested.append("statut_document")
    if criteria.proximity:
        requested.append("proximite")
    if criteria.viability:
        requested.append("viabilite")
    return requested


def _candidate_value(candidate: SearchCandidate, component: str) -> Any:
    return {
        "quartier": candidate.neighborhood,
        "prix": candidate.price_fcfa,
        "superficie": candidate.area_m2,
        "type_bien": candidate.property_type,
        "statut_document": candidate.document_status,
        "proximite": candidate.proximity,
        "viabilite": candidate.viability,
    }.get(component)


def score_candidate(
    criteria: SearchCriteria,
    candidate: SearchCandidate,
    weights: Mapping[str, float] = DEFAULT_WEIGHTS,
) -> RankedResult | None:
    """Calcule un score explicable ou exclut une contrainte impossible."""

    if candidate.age_days is not None and candidate.age_days > criteria.max_age_days:
        return None
    if (
        criteria.price_is_maximum
        and criteria.price_fcfa is not None
        and candidate.price_fcfa is not None
        and candidate.price_fcfa > criteria.price_fcfa
    ):
        return None

    requested = _requested_components(criteria)
    components: dict[str, float | None] = {
        "texte": cosine_similarity(criteria.description, candidate.text)
    }

    if criteria.neighborhood:
        components["quartier"] = (
            1.0
            if _normalized_equal(criteria.neighborhood, candidate.neighborhood)
            else (None if candidate.neighborhood is None else 0.0)
        )
    if criteria.price_fcfa is not None:
        if candidate.price_fcfa is None:
            components["prix"] = None
        elif criteria.price_is_maximum:
            components["prix"] = 1.0
        else:
            components["prix"] = numeric_similarity(
                criteria.price_fcfa, candidate.price_fcfa
            )
    if criteria.area_m2 is not None:
        components["superficie"] = (
            None
            if candidate.area_m2 is None
            else numeric_similarity(criteria.area_m2, candidate.area_m2)
        )
    categorical_pairs = {
        "type_bien": (criteria.property_type, candidate.property_type),
        "statut_document": (
            criteria.document_status,
            candidate.document_status,
        ),
        "proximite": (criteria.proximity, candidate.proximity),
        "viabilite": (criteria.viability, candidate.viability),
    }
    for component, (expected, observed) in categorical_pairs.items():
        if expected:
            components[component] = (
                None
                if observed is None
                else float(_normalized_equal(expected, observed))
            )

    for required in criteria.required_fields:
        if required not in requested:
            continue
        value = components.get(required)
        if value is None:
            return None
        if required in {
            "quartier",
            "type_bien",
            "statut_document",
            "proximite",
            "viabilite",
        } and value < 1:
            return None

    total_weight = sum(weights[name] for name in requested)
    available_weight = sum(
        weights[name]
        for name in requested
        if components.get(name) is not None
    )
    weighted_sum = sum(
        weights[name] * float(components[name])
        for name in requested
        if components.get(name) is not None
    )
    score = weighted_sum / total_weight if total_weight else 0.0
    coverage = available_weight / total_weight if total_weight else 0.0

    explanations: list[str] = []
    if components.get("quartier") == 1:
        explanations.append("Même quartier ou zone")
    if components.get("type_bien") == 1:
        explanations.append("Même type de bien")
    if components.get("prix") == 1 and criteria.price_is_maximum:
        explanations.append("Respecte le budget maximum")
    elif isinstance(components.get("prix"), float):
        explanations.append(
            f"Proximité de prix : {components['prix'] * 100:.0f} %"
        )
    if isinstance(components.get("superficie"), float):
        explanations.append(
            f"Proximité de superficie : {components['superficie'] * 100:.0f} %"
        )
    missing = [
        name
        for name in requested
        if name != "texte" and components.get(name) is None
    ]
    if missing:
        explanations.append(
            "Information absente : " + ", ".join(missing)
        )

    return RankedResult(
        candidate=candidate,
        score=round(score * 100, 2),
        coverage=round(coverage * 100, 2),
        components=components,
        explanations=tuple(explanations),
    )


def rank_candidates(
    criteria: SearchCriteria,
    candidates: Iterable[SearchCandidate],
    *,
    limit: int = 20,
) -> list[RankedResult]:
    results = [
        result
        for candidate in candidates
        if (result := score_candidate(criteria, candidate)) is not None
    ]
    results.sort(
        key=lambda result: (
            result.score,
            result.coverage,
            -(
                result.candidate.age_days
                if result.candidate.age_days is not None
                else criteria.max_age_days
            ),
        ),
        reverse=True,
    )
    return results[:limit]
