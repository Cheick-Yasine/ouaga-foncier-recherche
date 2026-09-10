"""Conservative, reproducible preparation; raw publications are never modified."""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone

from app.listing_scope import sale_eligible, within_ouagadougou
from app.neighborhoods import resolve_neighborhood, detect_out_of_scope_locality, neighborhood_key
from app.normalization import normalize_property_type
from app.offer_quality import offer_quality
from app.search_repository import _candidate_from_row

VERSION = 1
NUMBER = r'\d+(?:[ .,\u202f\u00a0]\d+)*'
AREA = re.compile(rf'(?P<n>{NUMBER})\s*(?P<u>m[²2]|hectares?|ha)\b', re.I)
PRICE = re.compile(rf'\bprix\s*(?:de\s*)?[:=]?\s*(?P<n>{NUMBER})\s*(?P<u>millions?|milliards?|fcfa|cfa)?', re.I)
SALE = re.compile(r'\b(?:en vente|a vendre|mis(?:e|es|s)? en vente|vend(?:s|ons)?|vente de|cession|a ceder)\b')


def number(value, unit=''):
    text = re.sub(r'[\s\u202f\u00a0]', '', str(value))
    if re.fullmatch(r'\d{1,3}(?:[.,]\d{3})+', text):
        text = re.sub(r'[.,]', '', text)
    else:
        text = text.replace(',', '.')
    value = float(text)
    return value * (1e9 if unit.lower().startswith('milliard') else 1e6 if unit.lower().startswith('million') else 10000 if unit.lower().startswith(('ha', 'hectare')) else 1)


def finite(value):
    if value is None or value == '':
        return None
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError('nombre_invalide')
    return value


def prepare_publication(source):
    """Return lots plus one auditable decision per source. Uncertain cases wait."""
    text = str(source.get('texte_nettoye') or source.get('resume_court') or '')
    normalized = neighborhood_key(text)
    if not sale_eligible(text):
        return [], 'location_demande_ou_indisponible'
    if not SALE.search(normalized):
        return [], 'vente_non_confirmee'
    if detect_out_of_scope_locality(text) or detect_out_of_scope_locality(source.get('quartier_zone')):
        return [], 'hors_perimetre'
    place = resolve_neighborhood(text, source.get('quartier_zone'))
    if not place.in_scope:
        return [], 'localisation_a_verifier'
    kind = normalize_property_type(source.get('type_bien_normalise') or source.get('type_bien'), text)
    if kind not in {'maison', 'terrain', 'parcelle'} or re.search(r'\bvillas?\b', normalized):
        return [], 'type_hors_perimetre_ou_ambigu'
    areas, prices = list(AREA.finditer(text)), list(PRICE.finditer(text))
    # Only an explicit repeating "Superficie ... Prix ..." layout is split.
    chunks = [(text, None, None)]
    if len(areas) > 1 or len(prices) > 1:
        if len(areas) != len(prices) or len(areas) < 2 or len(areas) > 20:
            return [], 'plusieurs_lots_a_verifier'
        starts = []
        for area in areas:
            label = re.search(r'(?:superficie|surface)\s*:?\s*$', text[:area.start()], re.I)
            if not label:
                return [], 'plusieurs_lots_a_verifier'
            starts.append(label.start())
        chunks = []
        for i, (area, price) in enumerate(zip(areas, prices)):
            end = starts[i+1] if i+1 < len(starts) else len(text)
            if not area.end() <= price.start() < end:
                return [], 'plusieurs_lots_a_verifier'
            chunks.append((text[:starts[0]] + text[starts[i]:end], area, price))
    lots = []
    try:
        for i, (lot_text, area_match, price_match) in enumerate(chunks):
            area_match = area_match or (areas[0] if areas else None)
            price_match = price_match or (prices[0] if prices else None)
            area = number(area_match['n'], area_match['u']) if area_match else finite(source.get('superficie_m2'))
            price = number(price_match['n'], price_match['u'] or '') if price_match else finite(source.get('prix_fcfa'))
            # Compound amounts such as "3 millions 500" are ambiguous here.
            if price_match and (price_match['u'] or '').lower().startswith(('million', 'milliard')) and re.match(r'\s*\d', text[price_match.end():]):
                return [], 'montant_compose_a_verifier'
            unit = re.search(r'(?:/|par)\s*(m[²2]|hectares?|ha)\b|\bl[’\x27](hectares?|ha)\b', lot_text, re.I)
            note = None
            if unit:
                if price is None or area is None:
                    return [], 'tarif_unitaire_surface_absente'
                # Preserve the advertised full lot rather than inventing a minimum lot.
                divisor = 1 if (unit[1] or '').lower().startswith('m') else 10000
                price *= area / divisor
                note = 'Prix total calculé pour la superficie annoncée'
            if price is None and area is None:
                return [], 'prix_et_superficie_absents'
            if price is not None and (not math.isfinite(price) or price < 10000):
                return [], 'prix_a_verifier'
            if area is not None and (not math.isfinite(area) or area <= 0):
                return [], 'superficie_a_verifier'
            row = dict(source, id=str(source['id']) if len(chunks) == 1 else f"{source['id']}::lot:{i+1}",
                       source_id=str(source['id']), lot_numero=i+1, texte_nettoye=lot_text,
                       resume_court=None, quartier_zone=place.canonical,
                       type_bien=kind, type_bien_normalise=kind, prix_fcfa=price, superficie_m2=area)
            candidate = _candidate_from_row(row, now=datetime.now(timezone.utc))
            candidate = replace(candidate, price_fcfa=price, area_m2=area, pricing_note=note)
            quality = offer_quality(candidate)
            row.update(qualite_preparee=quality, base_prix=note,
                       document_etat=quality['document_etat'], eau_etat=quality['eau_etat'],
                       electricite_etat=quality['electricite_etat'], statut_document=quality['document'],
                       dans_ouagadougou=within_ouagadougou(lot_text, place.canonical),
                       preparation_version=VERSION)
            lots.append(row)
    except (ValueError, TypeError, OverflowError):
        return [], 'chiffres_a_verifier'
    return lots, 'conserve'


def prepare_rows(rows):
    lots, audit, counts = [], [], Counter()
    for source in rows:
        prepared, reason = prepare_publication(source)
        counts[reason] += 1
        lots.extend(prepared)
        audit.append({'source_id': str(source['id']), 'motif': reason, 'lots': len(prepared)})
    return lots, audit, {'sources': len(audit), 'lots_prepares': len(lots), 'decisions': dict(counts), 'version': VERSION}
