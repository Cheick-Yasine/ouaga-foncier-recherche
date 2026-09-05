"""Analyse chiffrée d'une publication et sélection d'alternatives comparables."""
from __future__ import annotations

from dataclasses import replace
from statistics import median
import re
from typing import Any

from app.offer_quality import offer_quality, land_family, DOCUMENT_LABELS, PROXIMITY_LABELS
from app.text_features import normalize_text
from app.neighborhoods import resolve_neighborhood, CITY_LEVEL_AREAS, BROAD_AREAS
from app.search_engine import (
    SearchCandidate, SearchCriteria, numeric_similarity,
    parse_search_description, price_per_square_metre, rank_candidates,
    _same_announcement, _normalized_equal,
)


def local_neighborhood(text: str, fallback: str | None = None) -> str | None:
    """Conserve un lieu explicite, sans assimiler toute une ville à un quartier.

    Un nom hors référentiel reste une mention littérale, sans créer d'alias ni
    étendre le périmètre des annonces déjà chargées par le dépôt.
    """
    pattern = r"\b(?:à|a|localisation\s*:|quartier\s*:?)\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’ -]{1,55})"
    for match in re.finditer(pattern, text, re.IGNORECASE):
        name = re.split(r"\b(?:de|du|d'une|d’un|pour|avec|proche|près|pres|non|au|prix|superficie|surface|sur|en)\b", match[1], flags=re.IGNORECASE)[0].strip(" -")
        if not name or normalize_text(name).split()[0] in {"la", "le", "les", "une", "un", "des", "vendre", "saisir", "proximite", "cote", "partir", "confirmer", "debattre"}:
            continue
        resolution = resolve_neighborhood(name, None)
        if resolution.canonical:
            if resolution.canonical in CITY_LEVEL_AREAS | BROAD_AREAS:
                continue
            return resolution.canonical
        if len(name.split()) <= 3 and not re.search(r"(?i)\b(?:eau|electricite|électricité|voie|route|disponible|disponibilité|ecole|école)\b", name):
            return name.title()
    return fallback if fallback not in CITY_LEVEL_AREAS | BROAD_AREAS else None


def analyze_offer(publication: str, candidates: list[SearchCandidate], *, preferences: str = '', max_age_days: int = 30, required_fields: frozenset[str] = frozenset()) -> tuple[dict[str, Any], SearchCriteria, list]:
    parsed = parse_search_description(publication)
    neighborhood = local_neighborhood(publication, parsed.neighborhood)
    parsed = replace(parsed, neighborhood=neighborhood)
    if parsed.price_fcfa and re.search(r"\b(?:fcfa|f cfa|cfa)\s+(?:(?:par|le|au)\s+)?m2\b", normalize_text(publication)):
        parsed = replace(parsed, price_fcfa=parsed.price_fcfa * parsed.area_m2 if parsed.area_m2 else None)
    subject = SearchCandidate(identifier='publication-analysee', text=publication,
        property_type=parsed.property_type, neighborhood=parsed.neighborhood,
        price_fcfa=parsed.price_fcfa, area_m2=parsed.area_m2,
        document_status=parsed.document_status)
    preference = parse_search_description(preferences) if preferences else SearchCriteria(description='')
    # Les caractéristiques du vendeur ne deviennent pas des exigences pour les alternatives.
    criteria = replace(preference,
        description='Bonne affaire : ' + (preferences or 'offres comparables à l’annonce analysée'),
        property_type=preference.property_type or parsed.property_type,
        neighborhood=parsed.neighborhood,
        area_m2=preference.area_m2 or parsed.area_m2,
        max_age_days=max_age_days, required_fields=required_fields)
    description_parts = ["Bonne affaire", criteria.property_type or "bien immobilier"]
    if criteria.neighborhood: description_parts.append("à " + criteria.neighborhood)
    if criteria.area_m2: description_parts.append(f"environ {criteria.area_m2:.0f} m²")
    if criteria.price_fcfa:
        description_parts.append(("budget maximum " if criteria.price_is_maximum else "prix cible ") + f"{criteria.price_fcfa:.0f} FCFA")
    if criteria.document_status: description_parts.append("avec " + DOCUMENT_LABELS.get(criteria.document_status, criteria.document_status))
    if criteria.viability: description_parts.append(criteria.viability.replace("_", " "))
    if criteria.proximity: description_parts.extend(PROXIMITY_LABELS.get(p, p) for p in criteria.proximity.split("+"))
    criteria = replace(criteria, description=", ".join(description_parts))
    eligible = [replace(c, neighborhood=local_neighborhood(c.text, c.neighborhood)) for c in candidates if c.age_days is None or c.age_days <= max_age_days]
    others = [c for c in eligible if not _same_announcement(subject, c)]
    comparables = [c for c in others
        if parsed.neighborhood and _normalized_equal(c.neighborhood, parsed.neighborhood)
        and parsed.property_type and c.property_type == parsed.property_type
        and land_family(c) == land_family(subject)
        and parsed.area_m2 and c.area_m2 and 0.75 * parsed.area_m2 <= c.area_m2 <= 1.25 * parsed.area_m2
        and price_per_square_metre(c) is not None]
    # Même déduplication que la recherche, avant le calcul statistique.
    comparables = [r.candidate for r in rank_candidates(SearchCriteria(description='comparables'), comparables, limit=len(comparables))]
    quality = offer_quality(subject)
    unit_price = price_per_square_metre(subject)
    benchmark = median(price_per_square_metre(c) for c in comparables) if comparables else None
    delta = round((unit_price / benchmark - 1) * 100, 1) if unit_price is not None and benchmark else None
    sufficient = len(comparables) >= 3 and unit_price is not None
    reasons = list(quality['vigilances'])
    if quality['document_etat'] == 'mentionne': reasons.insert(0, 'Le document est mentionné, sa disponibilité reste à confirmer.')
    if unit_price is None:
        verdict = 'Prix au m² impossible à évaluer'
    elif not sufficient:
        verdict = 'Bonne affaire non confirmée : comparaison limitée'
    elif delta > 10:
        verdict = 'Prix élevé par rapport aux annonces comparables'
    elif delta < -10 and quality['indices']['document'] >= .7 and quality['indices']['viabilite'] >= .6 and quality['proximites']:
        verdict = 'Offre potentiellement intéressante, sous réserve de vérification'
    elif delta < -10:
        verdict = 'Prix intéressant, informations à compléter'
    else:
        verdict = 'Prix proche des annonces comparables'
    if sufficient:
        comparison = f"Prix au m² {abs(delta):g} % {'au-dessus' if delta > 0 else 'en dessous'} de la médiane de {len(comparables)} annonces de même type, même zone et superficie proche (± 25 %)."
    else:
        comparison = "Les annonces comparables du même quartier sont insuffisantes pour établir un repère de prix fiable."
    if sufficient and benchmark:
        comparison += f" Médiane observée : {benchmark:,.0f} FCFA/m².".replace(',', ' ')
    reasons.extend(quality['atouts'])
    analysis = {
        'verdict':verdict,'comparaison':comparison,'raisons':reasons,
        'bien':{'type_bien':subject.property_type,'quartier':subject.neighborhood,'prix_fcfa':subject.price_fcfa,'superficie_m2':subject.area_m2,'prix_m2_fcfa':unit_price,'document':quality['document']},
        'qualite':quality,'nombre_comparables':len(comparables),'mediane_prix_m2':benchmark,
        'ecart_mediane_pct':delta if sufficient else None,
        'portee':'Prix demandés dans les annonces, documents et équipements non vérifiés.',
    }
    # Aucun autre quartier ni hectare agricole ne devient une alternative locale.
    local_others = [c for c in others if neighborhood and _normalized_equal(c.neighborhood, neighborhood)
        and (not subject.property_type or c.property_type == subject.property_type)
        and land_family(c) == land_family(subject)
        and (not subject.area_m2 or c.area_m2 and .75 * subject.area_m2 <= c.area_m2 <= 1.25 * subject.area_m2)]
    alternatives = rank_candidates(criteria, local_others, limit=10)
    return analysis, criteria, alternatives
