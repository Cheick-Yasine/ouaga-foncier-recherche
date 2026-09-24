"""Moteur de recherche hybride : texte, critères métier et contraintes."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from app.offer_quality import offer_quality_from_neon, land_family_from_neon
from app.neighborhoods import detect_neighborhoods, resolve_neighborhood, neighborhood_metadata
from app.listing_scope import city_only_request
from app.normalization import normalize_property_type
from app.text_features import (
    extract_document_status,
    extract_document_statuses,
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
    city_only: bool = False
    area_min_m2: float | None = None
    area_max_m2: float | None = None
    neighborhoods: tuple[str, ...] = ()
    neighborhoods_strict: bool = False
    price_min_fcfa: float | None = None
    price_max_fcfa: float | None = None
    documents: tuple[str, ...] = ()
    documents_strict: bool = False


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
    numeric_text = re.sub(
        r"\b\d{1,3}(?:[.,]\d{3})+\b",
        lambda match: re.sub(r"[.,]", "", match.group()),
        description,
    )
    numeric_text = re.sub(
        r"(?<=\d)[.,](?=\d)",
        "decimalmark",
        numeric_text,
    )
    numeric_text = re.sub(
        r"(?i)(millions?|milliards?)(?=\d)",
        r"\1 ",
        numeric_text,
    )
    numeric_text = re.sub(
        r"(?i)(?<=\d)(?=(?:millions?|milliards?|fcfa|cfa)\b)",
        " ",
        numeric_text,
    )
    normalized = normalize_text(numeric_text).replace("decimalmark", ".")

    area_range = re.search(
        r"\bsuperficie entre (\d+(?:\.\d+)?) et (\d+(?:\.\d+)?) m2\b",
        normalized,
    )
    area_floor = re.search(
        r"\bsuperficie (?:minimum|au moins) (\d+(?:\.\d+)?) m2\b",
        normalized,
    )
    area_ceiling = re.search(
        r"\bsuperficie (?:maximum|au plus) (\d+(?:\.\d+)?) m2\b",
        normalized,
    )
    area_match = _AREA_PATTERN.search(normalized)
    hectare_match = _HECTARE_PATTERN.search(normalized)

    if area_match:
        area = _parse_number(area_match.group(1))
    elif hectare_match:
        area = _parse_number(hectare_match.group(1)) * 10_000
    else:
        area = None

    area_min = (
        float(area_range[1])
        if area_range
        else float(area_floor[1])
        if area_floor
        else None
    )
    area_max = (
        float(area_range[2])
        if area_range
        else float(area_ceiling[1])
        if area_ceiling
        else None
    )
    if area_range:
        area = (area_min + area_max) / 2
    elif area_floor:
        area = area_min
    elif area_ceiling:
        area = area_max

    text_without_area = normalized
    for matched in (area_range, area_floor, area_ceiling):
        if matched:
            text_without_area = (
                text_without_area[: matched.start()]
                + " "
                + text_without_area[matched.end() :]
            )
            break
    text_without_area = _AREA_PATTERN.sub(" ", text_without_area)
    text_without_area = _HECTARE_PATTERN.sub(" ", text_without_area)

    price_range = re.search(
        r"\b(?:prix|budget) entre (\d(?:[\d ]*\d)?(?:\.\d+)?) et "
        r"(\d(?:[\d ]*\d)?(?:\.\d+)?) (?:fcfa|f cfa|cfa)\b",
        text_without_area,
    )
    shared_unit_price_range = re.search(
        r"\b(?:prix|budget\s+)?entre\s+"
        r"(\d(?:[\d ]*\d)?(?:\.\d+)?)\s+et\s+"
        r"(\d(?:[\d ]*\d)?(?:\.\d+)?)\s*"
        r"(millions?|milliards?|fcfa|f cfa|cfa)\b",
        text_without_area,
    )
    price_floor = re.search(
        r"\bprix (?:minimum|au moins) (\d(?:[\d ]*\d)?(?:\.\d+)?) "
        r"(?:fcfa|f cfa|cfa)\b",
        text_without_area,
    )

    price_min: float | None = None
    price_max: float | None = None
    price: float | None = None

    if price_range or shared_unit_price_range:
        matched_range = price_range or shared_unit_price_range
        price_min = _parse_number(matched_range.group(1))
        price_max = _parse_number(matched_range.group(2))
        if shared_unit_price_range:
            unit = shared_unit_price_range.group(3)
            multiplier = (
                1_000_000_000
                if unit.startswith("milliard")
                else 1_000_000
                if unit.startswith("million")
                else 1
            )
            price_min *= multiplier
            price_max *= multiplier
        if price_min > price_max:
            price_min, price_max = price_max, price_min
        price = (price_min + price_max) / 2
    elif price_floor:
        price_min = _parse_number(price_floor.group(1))
        price = price_min
    else:
        price_match = _PRICE_PATTERN.search(text_without_area)
        budget_match = _BUDGET_PATTERN.search(text_without_area)
        if budget_match is not None:
            price_match = budget_match
        elif price_match is None:
            price_match = _PLAIN_PRICE_PATTERN.search(text_without_area)

        if price_match:
            price = _parse_number(price_match.group(1))
            unit = (
                price_match.group(2)
                if price_match.lastindex is not None
                and price_match.lastindex >= 2
                else None
            )
            if unit and unit.startswith("million"):
                price *= 1_000_000
                fraction = re.match(
                    r"\s+(\d{3})\b(?!\s+\d)",
                    text_without_area[price_match.end() :],
                )
                if fraction:
                    price += int(fraction.group(1)) * 1_000
            elif unit and unit.startswith("milliard"):
                price *= 1_000_000_000

    maximum_markers = (
        "budget",
        "maximum",
        "max ",
        "au plus",
        "ne pas depasser",
        "ne depasse pas",
        "jusqu a",
    )
    price_is_maximum = (
        price is not None
        and price_range is None
        and shared_unit_price_range is None
        and price_floor is None
        and any(marker in normalized for marker in maximum_markers)
    )
    if price_is_maximum:
        price_max = price

    if price is not None and (not math.isfinite(price) or price <= 0):
        price = None
    if price_min is not None and (
        not math.isfinite(price_min) or price_min <= 0
    ):
        price_min = None
    if price_max is not None and (
        not math.isfinite(price_max) or price_max <= 0
    ):
        price_max = None
    if area is not None and (not math.isfinite(area) or area <= 0):
        area = None

    property_type = normalize_property_type(None, description)
    detected = detect_neighborhoods(description)
    resolution = resolve_neighborhood(description, None)
    neighborhood = (
        detected[0]
        if len(detected) == 1
        else resolution.canonical
        if resolution.in_scope and not detected
        else None
    )
    neighborhoods = tuple(dict.fromkeys(detected))
    neighborhoods_strict = bool(
        neighborhoods
        and re.search(
            r"\buniquement dans (?:ces|les) zones\b",
            normalized,
        )
    )

    proximity = extract_proximity_details(description)
    viability = extract_viability(description)
    document_match = re.search(
        r"(?i)\bdocuments?\s+souhait[eé]s?\s*:\s*([^\.\n]+)",
        description,
    )
    documents: tuple[str, ...] = ()
    documents_strict = False
    if document_match:
        detected_documents: list[str] = []
        for raw_document in re.split(
            r"\s*,\s*|\s+ou\s+",
            document_match.group(1),
            flags=re.IGNORECASE,
        ):
            detected = extract_document_status(None, raw_document)
            if (
                detected != "non_precise"
                and detected not in detected_documents
            ):
                detected_documents.append(detected)
        documents = tuple(detected_documents)
        documents_strict = bool(documents)
        document = documents[0] if len(documents) == 1 else "non_precise"
    else:
        document = extract_document_status(None, description)

    return SearchCriteria(
        description=description.strip(),
        city_only=city_only_request(description),
        property_type=property_type,
        neighborhood=neighborhood,
        neighborhoods=neighborhoods,
        neighborhoods_strict=neighborhoods_strict,
        price_fcfa=price,
        price_min_fcfa=price_min,
        price_max_fcfa=price_max,
        price_is_maximum=price_is_maximum,
        area_m2=area,
        area_min_m2=area_min,
        area_max_m2=area_max,
        proximity=None if proximity == "non_precisee" else proximity,
        viability=None if viability == "non_precisee" else viability,
        document_status=None if document == "non_precise" else document,
        documents=documents,
        documents_strict=documents_strict,
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


def _requested_neighborhoods(criteria: SearchCriteria) -> tuple[str, ...]:
    if criteria.neighborhoods:
        return criteria.neighborhoods
    return (criteria.neighborhood,) if criteria.neighborhood else ()


def _requested_documents(criteria: SearchCriteria) -> tuple[str, ...]:
    if criteria.documents:
        return criteria.documents
    return (criteria.document_status,) if criteria.document_status else ()


def _document_matches(requested: str, observed: str) -> bool:
    if requested == "attestation_non_precisee":
        return observed.startswith("attestation_") or observed == "apfr"
    return requested == observed


def _requested_components(criteria: SearchCriteria) -> list[str]:
    requested = ["texte"]
    if _requested_neighborhoods(criteria):
        requested.append("quartier")
    if (
        criteria.price_fcfa is not None
        or criteria.price_min_fcfa is not None
        or criteria.price_max_fcfa is not None
    ):
        requested.append("prix")
    if criteria.area_m2 is not None:
        requested.append("superficie")
    if criteria.property_type:
        requested.append("type_bien")
    if _requested_documents(criteria):
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

    requested_neighborhoods = _requested_neighborhoods(criteria)
    neighborhood_match = (
        candidate.neighborhood is not None
        and any(
            _normalized_equal(name, candidate.neighborhood)
            for name in requested_neighborhoods
        )
    )
    if (
        criteria.neighborhoods_strict
        and requested_neighborhoods
        and not neighborhood_match
    ):
        return None

    requested_documents = _requested_documents(criteria)
    candidate_documents = extract_document_statuses(
        candidate.document_status,
        "",
    )
    document_match = bool(
        requested_documents
        and candidate_documents
        and any(
            _document_matches(requested, observed)
            for requested in requested_documents
            for observed in candidate_documents
        )
    )
    if (
        criteria.documents_strict
        and requested_documents
        and not document_match
    ):
        return None

    if criteria.price_min_fcfa is not None or criteria.price_max_fcfa is not None:
        if candidate.price_fcfa is None:
            return None
        if (
            criteria.price_min_fcfa is not None
            and candidate.price_fcfa < criteria.price_min_fcfa
        ):
            return None
        if (
            criteria.price_max_fcfa is not None
            and candidate.price_fcfa > criteria.price_max_fcfa
        ):
            return None

    if criteria.area_min_m2 is not None or criteria.area_max_m2 is not None:
        if candidate.area_m2 is None:
            return None
        if criteria.area_min_m2 is not None and candidate.area_m2 < criteria.area_min_m2:
            return None
        if criteria.area_max_m2 is not None and candidate.area_m2 > criteria.area_max_m2:
            return None
    if criteria.city_only:
        metadata = neighborhood_metadata(candidate.neighborhood)
        if (
            not metadata.get("in_scope")
            or metadata.get("zone_type") == "commune_peripherique"
        ):
            return None
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

    if requested_neighborhoods:
        components["quartier"] = (
            1.0
            if neighborhood_match
            or (
                criteria.city_only
                and "Ouagadougou" in requested_neighborhoods
            )
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
        "viabilite": (criteria.viability, candidate.viability),
    }
    for component, (expected, observed) in categorical_pairs.items():
        if expected:
            components[component] = (
                None
                if observed is None
                else float(_normalized_equal(expected, observed))
            )
    if requested_documents:
        document_state = "mentionne" if candidate.document_status else "non_precise"
        acceptable_document_states = {"mentionne"}
        if any(
            requested in {"recepisse", "croquis"}
            for requested in requested_documents
        ):
            acceptable_document_states.add("piece_annexe")
        components["statut_document"] = (
            float(
                document_match
                and document_state in acceptable_document_states
            )
            if candidate_documents
            else None
        )
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
        int(bool(_requested_neighborhoods(criteria)) and components.get("quartier") == 1),
        int(criteria.property_type is not None and components.get("type_bien") == 1),
        int(
            bool(_requested_documents(criteria))
            and components.get("statut_document") == 1
        ),
        int(criteria.proximity is not None and components.get("proximite") == 1),
        int(criteria.viability is not None and components.get("viabilite") == 1),
    )


def _price_match_priority(
    criteria: SearchCriteria,
    result: RankedResult,
) -> float:
    """Rapproche du montant demandé ; le plafond reste filtré avant le tri."""

    candidate_price = result.candidate.price_fcfa
    if (
        criteria.price_fcfa is None
        or candidate_price is None
    ):
        return -1.0 if criteria.price_fcfa is not None else 0.0
    match = numeric_similarity(criteria.price_fcfa, candidate_price)
    # Dans les 20 % sous un plafond, départager par surface et qualité.
    # Une offre à 27 M ne devance plus automatiquement une offre à 48 M
    # lorsque l'acheteur indique 50 M.
    if criteria.price_is_maximum and candidate_price >= criteria.price_fcfa * 0.8:
        return 1.0
    return match


def _is_good_deal_request(criteria: SearchCriteria) -> bool:
    normalized = normalize_text(criteria.description)
    return any(marker in normalized for marker in _GOOD_DEAL_MARKERS)


def _comparable_priority(criteria: SearchCriteria, result: RankedResult) -> float:
    candidate = result.candidate
    if criteria.area_m2 is not None:
        match = numeric_similarity(criteria.area_m2, candidate.area_m2) if candidate.area_m2 else 0.0
        return float(match >= 0.8) if _is_good_deal_request(criteria) else round(match, 3)
    if _is_good_deal_request(criteria) and criteria.property_type in {None, "parcelle"}:
        return float(candidate.property_type == "parcelle" and land_family_from_neon(candidate) != "grand_terrain")
    return 0.0


def _completeness_priority(quality: dict) -> tuple:
    """La présence d'informations utiles prime sur le prix, sans inventer leur disponibilité."""
    indices = quality["indices"]
    document = indices["document"] >= 0.7
    utilities = sum(quality[key] in {"mentionne", "annonce_disponible"} for key in ("eau_etat", "electricite_etat"))
    proximity_count = len(quality["proximites"])
    completeness = int(document) + utilities + min(proximity_count, 2)
    return (int(quality["informations_completes"]), int(document), completeness, indices["document"], indices["viabilite"], proximity_count)


def _recommendation_priority(criteria: SearchCriteria, result: RankedResult, quality: dict | None = None) -> tuple:
    """Ordre commun au moteur local et au filtre sémantique."""
    quality = quality if quality is not None else offer_quality_from_neon(result.candidate)
    return (
        _descriptive_priority(criteria, result),
        _price_match_priority(criteria, result),
        _comparable_priority(criteria, result),
        _completeness_priority(quality),
        -(price_per_square_metre(result.candidate) or float("inf")),
        -(result.candidate.price_fcfa or float("inf")),
        result.score,
        result.candidate.area_m2 or 0.0 if _is_good_deal_request(criteria) else result.coverage,
        -(
            result.candidate.age_days
            if result.candidate.age_days is not None
            else float("inf")
        ),
    )


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
    qualities = {
        result.candidate.identifier: offer_quality_from_neon(result.candidate)
        for result in results
    }
    if good_deal:
        results = [replace(result, explanations=result.explanations + (
            " ; ".join(qualities[result.candidate.identifier]["atouts"])
            or "Informations limitées : documents et équipements à préciser",
        )) for result in results]

    results.sort(key=lambda result: _recommendation_priority(criteria, result, qualities[result.candidate.identifier]), reverse=True)
    return results[:limit]
