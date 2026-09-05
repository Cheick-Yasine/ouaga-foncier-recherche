"""Moteur de recherche hybride : texte, critères métier et contraintes."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from app.offer_quality import land_family, offer_quality, document_evidence
from app.neighborhoods import resolve_neighborhood
from app.normalization import normalize_property_type
from app.text_features import (
    extract_document_status,
    extract_proximity_details,
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
    r"\b((?:\d{1,3}(?: \d{3})+|\d+)(?:[.,]\d+)?)\s*(?:m2|metres? carres?)\b"
)
_HECTARE_PATTERN = re.compile(
    r"\b(\d+(?:[.,]\d+)?)\s*(?:hectares?|ha)\b"
)
_PRICE_PATTERN = re.compile(
    r"\b(\d[\d ]*(?:[.,]\d+)?|un)\s*"
    r"(milliards?|millions?|fcfa|f cfa|cfa)\b"
)
_PLAIN_PRICE_PATTERN = re.compile(
    r"\b(?:prix(?:\s+de)?|a|de|pour)\s*"
    r"(\d(?:[\d ]*\d)?)\b"
)
_BUDGET_PATTERN = re.compile(
    r"\bbudget(?:\s+(?:maximum|maximal|de))?\s*"
    r"(\d[\d ]*(?:[.,]\d+)?)\s*"
    r"(milliards?|millions?|fcfa|f cfa|cfa)?\b"
)
_GOOD_DEAL_MARKERS = (
    "bon deal",
    "bonne affaire",
    "meilleur deal",
    "bon prix",
    "meilleur prix",
    "prix interessant",
    "prix avantageux",
    "bonnes affaires",
    "meilleure offre",
    "meilleures offres",
    "bon dill",
    "bons deals",
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
    max_age_days: int | None = None


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
    publication_label: str | None = None
    collected_at: str | None = None
    contact: str | None = None
    pricing_note: str | None = None


@dataclass(frozen=True)
class RankedResult:
    candidate: SearchCandidate
    score: float
    coverage: float
    components: Mapping[str, float | None]
    explanations: tuple[str, ...]


def _parse_number(value: str) -> float:
    compact = value.replace(" ", "").replace(",", ".")
    if compact == "un":
        return 1.0
    return float(compact)


def parse_search_description(description: str) -> SearchCriteria:
    """Interprète les critères explicites d'une description utilisateur."""

    # La normalisation textuelle efface les virgules : préserver 6,5 millions.
    numeric_text = re.sub(r"\b\d{1,3}(?:[.,]\d{3})+\b", lambda m: re.sub(r"[.,]", "", m.group()), description)
    numeric_text = re.sub(r"(?<=\d)[.,](?=\d)", "decimalmark", numeric_text)
    numeric_text = re.sub(r"(?i)(millions?|milliards?)(?=\d)", r"\1 ", numeric_text)
    normalized = normalize_text(numeric_text).replace("decimalmark", ".")
    area_match = _AREA_PATTERN.search(normalized)
    hectare_match = _HECTARE_PATTERN.search(normalized)
    if area_match:
        area = _parse_number(area_match.group(1))
    elif hectare_match:
        area = _parse_number(hectare_match.group(1)) * 10_000
    else:
        area = None

    text_without_area = _AREA_PATTERN.sub(" ", normalized)
    text_without_area = _HECTARE_PATTERN.sub(" ", text_without_area)
    price_match = _PRICE_PATTERN.search(text_without_area)
    budget_match = _BUDGET_PATTERN.search(text_without_area)
    if budget_match is not None:
        price_match = budget_match
    elif price_match is None:
        price_match = _PLAIN_PRICE_PATTERN.search(text_without_area)

    price: float | None = None
    if price_match:
        price = _parse_number(price_match.group(1))
        unit = (
            price_match.group(2)
            if price_match.lastindex is not None and price_match.lastindex >= 2
            else None
        )
        if unit and unit.startswith("million"):
            price *= 1_000_000
            fraction = re.match(r"\s+(\d{3})\b(?!\s+\d)", text_without_area[price_match.end():])
            if fraction:
                price += int(fraction.group(1)) * 1_000
        elif unit and unit.startswith("milliard"):
            price *= 1_000_000_000

    if price is not None and (not math.isfinite(price) or price <= 0):
        price = None
    if area is not None and (not math.isfinite(area) or area <= 0):
        area = None
    property_type = normalize_property_type(None, description)
    resolution = resolve_neighborhood(description, None)
    neighborhood = resolution.canonical if resolution.in_scope else None

    proximity = extract_proximity_details(description)
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
    if left_vector == right_vector:
        return 1.0
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


def price_per_square_metre(candidate: SearchCandidate) -> float | None:
    """Calcule le prix total ramené au m² lorsque les deux valeurs sont fiables."""

    price = candidate.price_fcfa
    area = candidate.area_m2
    if price is None or area is None or not math.isfinite(price) or not math.isfinite(area) or price <= 0 or area <= 0:
        return None
    return round(price / area, 2)


def _normalized_equal(left: str | None, right: str | None) -> bool:
    return bool(left and right and normalize_text(left) == normalize_text(right))


def _same_optional_value(left: str | None, right: str | None) -> bool:
    """Deux valeurs absentes sont équivalentes pour identifier une republication."""

    if left is None or right is None:
        return left is right
    return _normalized_equal(left, right)


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


def score_candidate(
    criteria: SearchCriteria,
    candidate: SearchCandidate,
    weights: Mapping[str, float] = DEFAULT_WEIGHTS,
) -> RankedResult | None:
    """Calcule un score explicable ou exclut une contrainte impossible."""

    if (
        criteria.max_age_days is not None
        and candidate.age_days is not None
        and candidate.age_days > criteria.max_age_days
    ):
        return None
    if criteria.price_is_maximum and criteria.price_fcfa is not None:
        # Sans prix vérifiable, impossible d'affirmer que le budget est respecté.
        if candidate.price_fcfa is None:
            return None
        if candidate.price_fcfa > criteria.price_fcfa:
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
        "viabilite": (criteria.viability, candidate.viability),
    }
    for component, (expected, observed) in categorical_pairs.items():
        if expected:
            components[component] = (
                None
                if observed is None
                else float(_normalized_equal(expected, observed))
            )
    if criteria.document_status:
        document, document_state, _, _ = document_evidence(candidate)
        match = _normalized_equal(criteria.document_status, document)
        if criteria.document_status == "attestation_non_precisee" and document:
            match = document.startswith("attestation_") or document == "apfr"
        components["statut_document"] = float(match and document_state in {"mentionne", "annonce_disponible"}) if document else None
    if criteria.viability:
        quality = offer_quality(candidate)
        expected_utilities = {"eau"} if criteria.viability == "eau" else {"electricite"} if criteria.viability == "electricite" else {"eau", "electricite"}
        components["viabilite"] = float(all(quality[name + "_etat"] in {"mentionne", "annonce_disponible"} for name in expected_utilities))

    if criteria.proximity:
        if candidate.proximity is None:
            components["proximite"] = None
        else:
            requested_proximities = set(criteria.proximity.split("+"))
            observed_proximities = set(candidate.proximity.split("+"))
            components["proximite"] = float(
                requested_proximities <= observed_proximities
            )
        # Une proximité formulée explicitement est une caractéristique réelle,
        # pas un simple mot-clé : une annonce non conforme est écartée.
        if components["proximite"] != 1:
            return None

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


def _contact_numbers(value: str | None) -> frozenset[str]:
    """Normalise les téléphones sans les exposer hors du moteur local."""

    if not value:
        return frozenset()
    matches = re.findall(r"(?:\+?226[\s()./-]*)?(?:\d[\s()./-]*){8}", value)
    numbers = {
        "".join(re.findall(r"\d", match))[-8:]
        for match in matches
    }
    return frozenset(number for number in numbers if len(number) == 8)


def _same_announcement(
    candidate: SearchCandidate,
    other: SearchCandidate,
) -> bool:
    if candidate.identifier == other.identifier:
        return True
    same_characteristics = (
        candidate.price_fcfa is not None
        and other.price_fcfa is not None
        and candidate.area_m2 is not None
        and other.area_m2 is not None
        and candidate.price_fcfa == other.price_fcfa
        and candidate.area_m2 == other.area_m2
        and _same_optional_value(candidate.neighborhood, other.neighborhood)
        and _same_optional_value(candidate.property_type, other.property_type)
    )
    if not same_characteristics:
        return False
    shared_contacts = (
        _contact_numbers(candidate.contact)
        & _contact_numbers(other.contact)
    )
    if shared_contacts:
        return True

    # Les republications inter-groupes sont souvent reformulées. Le cosinus
    # mots + bigrammes reconnaît les mêmes sites et repères sans exiger un
    # texte copié mot pour mot.
    return cosine_similarity(candidate.text, other.text) >= 0.50


def _descriptive_priority(
    criteria: SearchCriteria,
    result: RankedResult,
) -> tuple[int, int, int, int, int]:
    """Place les critères descriptifs explicites avant prix et superficie."""

    components = result.components
    return (
        int(criteria.neighborhood is not None and components.get("quartier") == 1),
        int(criteria.property_type is not None and components.get("type_bien") == 1),
        int(
            criteria.document_status is not None
            and components.get("statut_document") == 1
        ),
        int(criteria.proximity is not None and components.get("proximite") == 1),
        int(criteria.viability is not None and components.get("viabilite") == 1),
    )


def _price_match_priority(
    criteria: SearchCriteria,
    result: RankedResult,
) -> float:
    """Un prix demandé sans notion de budget est une cible, pas un plafond."""

    candidate_price = result.candidate.price_fcfa
    if (
        criteria.price_fcfa is None
        or criteria.price_is_maximum
        or candidate_price is None
    ):
        return 0.0
    return numeric_similarity(criteria.price_fcfa, candidate_price)


def _is_good_deal_request(criteria: SearchCriteria) -> bool:
    normalized = normalize_text(criteria.description)
    return any(marker in normalized for marker in _GOOD_DEAL_MARKERS)


def _comparable_priority(criteria: SearchCriteria, result: RankedResult) -> float:
    candidate = result.candidate
    if criteria.area_m2 is not None:
        match = numeric_similarity(criteria.area_m2, candidate.area_m2) if candidate.area_m2 else 0.0
        return float(match >= 0.8) if _is_good_deal_request(criteria) else round(match, 3)
    if _is_good_deal_request(criteria) and criteria.property_type in {None, "parcelle"}:
        return float(candidate.property_type == "parcelle" and land_family(candidate) != "grand_terrain")
    return 0.0


def _completeness_priority(quality: dict) -> tuple:
    """La présence d'informations utiles prime sur le prix, sans inventer leur disponibilité."""
    indices = quality["indices"]
    document = indices["document"] >= 0.7
    utilities = sum(quality[key] in {"mentionne", "annonce_disponible"} for key in ("eau_etat", "electricite_etat"))
    proximity_count = len(quality["proximites"])
    completeness = int(document) + utilities + min(proximity_count, 2)
    return (int(quality["informations_completes"]), int(document), completeness, indices["document"], indices["viabilite"], proximity_count)


def rank_candidates(
    criteria: SearchCriteria,
    candidates: Iterable[SearchCandidate],
    *,
    limit: int = 20,
) -> list[RankedResult]:
    unique_candidates: list[SearchCandidate] = []
    for candidate in candidates:
        if any(
            _same_announcement(candidate, other)
            for other in unique_candidates
        ):
            continue
        unique_candidates.append(candidate)

    results = [
        result
        for candidate in unique_candidates
        if (result := score_candidate(criteria, candidate)) is not None
    ]
    good_deal = _is_good_deal_request(criteria)
    qualities = {result.candidate.identifier: offer_quality(result.candidate) for result in results}
    if good_deal:
        results = [replace(result, explanations=result.explanations + (
            " ; ".join(qualities[result.candidate.identifier]["atouts"])
            or "Informations limitées : documents et équipements à préciser",
        )) for result in results]

    results.sort(
        key=lambda result: (
            _descriptive_priority(criteria, result),
            _price_match_priority(criteria, result),
            _comparable_priority(criteria, result),
            _completeness_priority(qualities[result.candidate.identifier]),
            -(price_per_square_metre(result.candidate) or float("inf")),
            -(result.candidate.price_fcfa or float("inf")),
            result.score,
            result.candidate.area_m2 or 0.0 if good_deal else result.coverage,
            -(
                result.candidate.age_days
                if result.candidate.age_days is not None
                else float("inf")
            ),
        ),
        reverse=True,
    )
    return results[:limit]
