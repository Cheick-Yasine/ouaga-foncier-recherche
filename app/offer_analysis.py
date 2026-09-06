"""Analyse chiffrée d'une publication et sélection d'alternatives comparables."""
from __future__ import annotations
from app.neighborhoods import local_neighborhood

from dataclasses import dataclass, field, replace
from statistics import median
import re
from typing import Any

from app.offer_quality import offer_quality, land_family, DOCUMENT_LABELS, PROXIMITY_LABELS
from app.text_features import normalize_text
from app.neighborhoods import resolve_neighborhood, CITY_LEVEL_AREAS, BROAD_AREAS
from app.neighborhood_geo import NEARBY_RADIUS_KM, location_for, neighborhood_relation
from app.search_engine import (
    RankedResult, SearchCandidate, SearchCriteria,
    parse_search_description, price_per_square_metre, rank_candidates,
    _same_announcement,
)


@dataclass(frozen=True)
class OfferAlternative(RankedResult):
    comparison: dict[str, Any] = field(default_factory=dict)


_UTILITY_LEVEL = {'non_precise': 0, 'absent': 0, 'prevu': 0,
                  'proximite': .2, 'mentionne': .6, 'annonce_disponible': 1}


def _proximities(quality: dict) -> set[str]:
    items = set(quality['proximites'])
    if items & {'voie_bitumee', 'acces_voie_bitumee'}:
        items.add('voie_route')
    return items


def _better_option(subject: SearchCandidate, candidate: SearchCandidate,
                   original: dict, quality: dict, budget: float | None) -> dict | None:
    """Un prix bas seul ne suffit pas : garder les atouts déjà renseignés.

    Les indices comparent la précision des annonces, pas la valeur juridique
    des titres. Un supplément de prix reste explicite et dans le budget.
    """
    price = price_per_square_metre(candidate)
    reference = price_per_square_metre(subject)
    if not price or not candidate.price_fcfa or quality['indices']['document'] < .7:
        return None
    ceiling = budget or subject.price_fcfa
    if ceiling is not None and candidate.price_fcfa > ceiling:
        return None
    old_levels = [original['indices']['document'], *(_UTILITY_LEVEL[original[k + '_etat']] for k in ('eau', 'electricite'))]
    new_levels = [quality['indices']['document'], *(_UTILITY_LEVEL[quality[k + '_etat']] for k in ('eau', 'electricite'))]
    old_prox, new_prox = _proximities(original), _proximities(quality)
    if any(new < old for old, new in zip(old_levels, new_levels)) or not old_prox <= new_prox:
        return None
    risks = {'Bas-fond ou caractère inondable mentionné', 'Terrain annoncé non loti'}
    if (set(quality['vigilances']) & risks) - set(original['vigilances']):
        return None
    cheaper = reference is not None and price < reference
    clearer = new_levels != old_levels or new_prox > old_prox
    if not cheaper and not clearer:
        return None
    advantages, tradeoffs = [], []
    delta = round((price / reference - 1) * 100, 1) if reference else None
    if cheaper:
        advantages.append(f"Prix au m² plus bas : {price:,.0f} FCFA/m² contre {reference:,.0f} FCFA/m²".replace(',', ' '))
    elif reference and price > reference:
        tradeoffs.append('Prix au m² plus élevé que celui de votre annonce')
    if subject.price_fcfa and candidate.price_fcfa > subject.price_fcfa:
        extra = candidate.price_fcfa - subject.price_fcfa
        tradeoffs.append(f"Budget supplémentaire : {extra:,.0f} FCFA".replace(',', ' '))
    if new_levels[0] > old_levels[0]:
        advantages.append(DOCUMENT_LABELS.get(quality['document'], 'Document') + (' annoncé disponible' if quality['document_etat'] == 'annonce_disponible' else ' mentionné dans l’annonce'))
    for index, (key, label) in enumerate((('eau', 'Eau'), ('electricite', 'Électricité')), 1):
        if new_levels[index] > old_levels[index]:
            state = quality[key + '_etat']
            suffix = ' annoncée sur place' if state == 'annonce_disponible' else ' mentionnée, raccordement à confirmer' if state == 'mentionne' else ' à proximité, raccordement à confirmer'
            advantages.append(label + suffix)
    advantages.extend(PROXIMITY_LABELS[p] for p in quality['proximites'] if p not in old_prox)
    if original['document'] and quality['document'] != original['document']:
        tradeoffs.append('Document différent : ' + DOCUMENT_LABELS.get(quality['document'], 'à préciser'))
    return {'avantages': advantages, 'compromis': tradeoffs, 'ecart_prix_m2_pct': delta}


def _summary(subject: SearchCandidate, quality: dict, comparison: str,
             alternatives: list[OfferAlternative], budget: float | None) -> str:
    """Faits simples que le modèle peut développer sans inventer un verdict."""
    parts = []
    if subject.price_fcfa and subject.area_m2:
        parts.append(f"Cette offre est annoncée à {subject.price_fcfa:,.0f} FCFA pour {subject.area_m2:g} m², soit {price_per_square_metre(subject):,.0f} FCFA/m².".replace(',', ' '))
    else:
        parts.append('Il manque le prix total ou la surface pour calculer le prix au m².')
    if budget and subject.price_fcfa:
        parts.append('Elle respecte votre budget.' if subject.price_fcfa <= budget else 'Elle dépasse votre budget.')
    parts.append(comparison)
    if quality['atouts']:
        parts.append('Ses points forts annoncés : ' + '; '.join(quality['atouts']) + '.')
    missing = list(quality['vigilances'])
    if quality['document_etat'] == 'mentionne':
        missing.insert(0, 'la disponibilité du document reste à confirmer')
    if missing:
        parts.append('À vérifier avant de choisir : ' + '; '.join(missing) + '.')
    if alternatives:
        first = alternatives[0]
        relation = first.comparison
        where = 'dans le même quartier' if relation['meme_quartier'] else relation['distance_libelle'] + ' en ligne droite entre les quartiers'
        parts.append(f"L’offre à {first.candidate.neighborhood}, {where}, mérite d’être regardée : " + '; '.join(relation['avantages']) + '.')
        if relation['compromis']:
            parts.append('En contrepartie : ' + '; '.join(relation['compromis']) + '.')
    else:
        parts.append('Je n’ai pas trouvé d’offre clairement meilleure dans la zone comparée. Cela ne suffit pas à dire que celle-ci est la meilleure.')
    parts.append('Les documents et les équipements restent à vérifier auprès du vendeur.')
    return ' '.join(parts)



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
        neighborhood=preference.neighborhood or parsed.neighborhood,
        area_m2=preference.area_m2 or parsed.area_m2,
        price_is_maximum=bool(preference.price_fcfa),
        max_age_days=max_age_days, required_fields=required_fields | preference.required_fields)
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
        if parsed.neighborhood and (neighborhood_relation(parsed.neighborhood, c.neighborhood) or {}).get('meme_quartier')
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
        comparison = (f"Son prix au m² est {abs(delta):g} % {'plus élevé' if delta > 0 else 'plus bas'} que le prix de repère des offres similaires du quartier." if delta else 'Son prix au m² est au niveau du prix de repère des offres similaires du quartier.')
    else:
        comparison = "Il n’y a pas assez d’annonces similaires dans ce quartier pour dire si ce prix est bas ou élevé."
    if sufficient and benchmark:
        comparison += f" Ce repère est d’environ {benchmark:,.0f} FCFA/m² ; il repose sur les prix demandés par les vendeurs.".replace(',', ' ')
    reasons.extend(quality['atouts'])
    analysis = {
        'verdict':verdict,'comparaison':comparison,'raisons':reasons,
        'bien':{'type_bien':subject.property_type,'quartier':subject.neighborhood,'prix_fcfa':subject.price_fcfa,'superficie_m2':subject.area_m2,'prix_m2_fcfa':unit_price,'document':quality['document']},
        'qualite':quality,'nombre_comparables':len(comparables),'mediane_prix_m2':benchmark,
        'ecart_mediane_pct':delta if sufficient else None,
        'portee':'Prix demandés dans les annonces, documents et équipements non vérifiés.',
    }
    strict_zone = 'quartier' in criteria.required_fields or bool(re.search(r'\b(?:(?:uniquement|seulement|exclusivement)\s+(?:a|au|dans)|meme quartier|pas d.autres? quartiers?)\b', normalize_text(preferences)))
    origin = criteria.neighborhood
    metadata = {}
    pool = []
    for candidate in others:
        relation = neighborhood_relation(origin, candidate.neighborhood)
        if not relation or (strict_zone and not relation['meme_quartier']):
            continue
        if criteria.property_type and candidate.property_type != criteria.property_type:
            continue
        if land_family(candidate) != land_family(subject):
            continue
        if criteria.area_m2 and (not candidate.area_m2 or not .75 * criteria.area_m2 <= candidate.area_m2 <= 1.25 * criteria.area_m2):
            continue
        candidate_quality = offer_quality(candidate)
        option = _better_option(subject, candidate, quality, candidate_quality, criteria.price_fcfa)
        if not option:
            continue
        metadata[candidate.identifier] = {**relation, **option}
        pool.append(replace(candidate, proximity='+'.join(candidate_quality['proximites']) or None))
    # La proximité a été vérifiée géographiquement. Elle n'est pas une égalité
    # de quartier ; le budget et les autres exigences restent actifs.
    explicit = {name for name, value in [('statut_document', criteria.document_status), ('viabilite', criteria.viability), ('proximite', criteria.proximity)] if value}
    ranking_criteria = replace(criteria, neighborhood=None, required_fields=(criteria.required_fields | explicit) - {'quartier'})
    ranked = rank_candidates(ranking_criteria, pool, limit=len(pool))
    # Une offre complète reste prioritaire. À complétude comparable, préférer
    # le quartier demandé à ses voisins et conserver le classement prix/qualité.
    ranked.sort(key=lambda r: (not offer_quality(r.candidate)['informations_completes'],
                               not metadata[r.candidate.identifier]['meme_quartier']))
    alternatives = [OfferAlternative(**vars(r), comparison=metadata[r.candidate.identifier]) for r in ranked[:10]]
    analysis['zone_recherche'] = {
        'quartier_origine': origin, 'quartiers_proches_inclus': not strict_zone and location_for(origin) is not None,
        'rayon_km': NEARBY_RADIUS_KM if not strict_zone and location_for(origin) else None,
        'precision': 'Distances approximatives entre les quartiers, en ligne droite. Le trajet par la route peut être plus long.',
    }
    analysis['resume'] = _summary(subject, quality, comparison, alternatives, criteria.price_fcfa)
    return analysis, criteria, alternatives
