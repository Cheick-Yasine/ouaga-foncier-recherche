"""Indices annoncés, sans assimiler une mention à une vérification sur place."""
from __future__ import annotations

import re
from typing import Any, TYPE_CHECKING

from app.text_features import extract_document_status, extract_proximity_details, normalize_text

if TYPE_CHECKING:
    from app.search_engine import SearchCandidate

DOCUMENT_LABELS = {
    'apfr': 'APFR', 'puh': 'PUH', 'titre_foncier': 'Titre foncier',
    'attestation_possession': 'Attestation de possession',
    'attestation_attribution': 'Attestation d’attribution',
    'attestation_non_precisee': 'Attestation (type non précisé)',
    'plusieurs_documents': 'Plusieurs documents',
    'recepisse': 'Récépissé de dépôt', 'croquis': 'Croquis',
}
PROXIMITY_LABELS = {
    'ecole': 'École à proximité', 'centre_sante_hopital': 'Centre de santé à proximité',
    'voie_bitumee': 'Voie bitumée à proximité', 'voie_route': 'Route mentionnée',
    'acces_voie_bitumee': 'Accès bitumé annoncé', 'marche': 'Marché à proximité',
}
DOC_WORD = r'(?:apfr|puh|titre foncier|attestation(?: de possession(?: fonciere rurale)?)?|documents?|papiers?)'
ABSENT_DOC = re.compile(rf'\b(?:sans|aucun|pas de)\s+{DOC_WORD}\b|\b{DOC_WORD}\s+(?:absent|indisponible|non disponible)')
PENDING = re.compile(r'\b(?:en cours|en attente|depose\w*|demande\w*|a etablir|a fournir|a delivrer|non delivre\w*|non encore|pas encore)\b')
AVAILABLE = re.compile(r'\b(?:disponible\w*|delivre\w*|en main|en possession|obtenu\w*|remis\w*)\b')


def document_evidence(candidate: SearchCandidate) -> tuple[str | None, str, str, float]:
    text = normalize_text(candidate.text)
    document = extract_document_status(candidate.document_status, candidate.text)
    document = None if document == 'non_precise' else document
    windows = [text[max(0,m.start()-25):m.end()+65] for m in re.finditer(DOC_WORD, text)]
    if ABSENT_DOC.search(text):
        return document, 'absent', 'Document annoncé absent', 0.0
    if re.search(r'\b(?:recepisse|croquis)\b', text) and document is None:
        kind = 'recepisse' if 'recepisse' in text else 'croquis'
        return kind, 'piece_annexe', 'Pièce mentionnée, document foncier à préciser', 0.1
    if windows and any(PENDING.search(w) for w in windows):
        return document, 'en_cours', 'Démarche en cours, délivrance non confirmée', 0.15
    if document:
        if any(AVAILABLE.search(w) for w in windows):
            return document, 'annonce_disponible', 'Disponibilité annoncée, à vérifier', 1.0
        return document, 'mentionne', 'Mentionné, disponibilité à confirmer', 0.7
    return None, 'non_precise', 'Document non précisé', 0.0


def _utility(text: str, pattern: str, structured: bool) -> tuple[str, float]:
    matches = list(re.finditer(pattern, text))
    if not matches:
        return ('mentionne', 0.6) if structured else ('non_precise', 0.0)
    for match in matches:
        before, after = text[max(0,match.start()-32):match.start()], text[match.end():match.end()+45]
        if re.search(r'\b(?:sans|pas de|absence de|aucun|ni)(?:\s+\w+){0,4}\s*$', before) or re.match(r'\s+(?:absente?|indisponible|non disponible|non raccorde)', after):
            return 'absent', 0.0
    windows = [text[max(0,m.start()-22):m.start()].split('|')[-1] + text[m.start():m.end()+45].split('|')[0] for m in matches]
    if any(re.search(r'\b(?:bientot|prevu|a venir|en cours|projet|en attente)\b', w) for w in windows):
        return 'prevu', 0.0
    if any(re.search(r'\b(?:proche|proximite|non loin|a cote|a \d+ m)\b', w) for w in windows):
        return 'proximite', 0.2
    if any(re.search(r'\b(?:raccorde\w*|branche\w*|compteur\w*|disponible\w*|sur place)\b', w) for w in windows):
        return 'annonce_disponible', 1.0
    return 'mentionne', 0.6


def offer_quality(candidate: SearchCandidate) -> dict[str, Any]:
    # Garder une séparation entre phrases pour ne pas rattacher « proche du
    # goudron » à l'eau annoncée disponible dans la phrase précédente.
    text = " | ".join(normalize_text(part) for part in re.split(r"[.!?;\n]+", candidate.text))
    document, state, doc_label, doc_score = document_evidence(candidate)
    water, water_score = _utility(text, r'\b(?:eau|onea|forage)\b', candidate.viability in {'eau','eau_et_electricite'})
    electricity, elec_score = _utility(text, r'\b(?:electricite|sonabel|courant|reseau electrique)\b', candidate.viability in {'electricite','eau_et_electricite'})
    if re.search(r'\bnon viabilise\w*\b', text):
        water_score = elec_score = 0.0
        water = electricity = 'non_precise'
    detected = extract_proximity_details(candidate.text)
    proximities = set((candidate.proximity or '').split('+')) | set(detected.split('+'))
    if re.search(r'\b(?:proche|proximite|non loin|a cote|face|apres)(?:\s+\w+){0,5}\s+marche\b', text):
        proximities.add('marche')
    proximities &= PROXIMITY_LABELS.keys()
    # Une négation explicite ne rapporte jamais de points de proximité.
    if re.search(r'\b(?:loin du|loin de|aucune proximite)\b', text) and not re.search(r'\bnon loin\b', text):
        proximities.clear()
    strengths: list[str] = []
    warnings: list[str] = []
    if state in {'mentionne','annonce_disponible'}:
        strengths.append(DOCUMENT_LABELS.get(document, 'Document') + (' annoncé disponible' if state == 'annonce_disponible' else ' mentionné'))
    else:
        warnings.append(doc_label)
    for name, status in (('Eau',water),('Électricité',electricity)):
        if status == 'annonce_disponible': strengths.append(name + ' annoncée sur place')
        elif status == 'mentionne': strengths.append(name + ' mentionnée (raccordement à confirmer)')
        elif status == 'proximite': warnings.append(name + ' à proximité, raccordement non confirmé')
        elif status == 'prevu': warnings.append(name + ' prévue, disponibilité non confirmée')
        elif status == 'absent': warnings.append(name + ' annoncée absente')
    if water == electricity == 'non_precise':
        warnings.append('Eau et électricité non précisées')
    strengths.extend(PROXIMITY_LABELS[p] for p in sorted(proximities))
    if not proximities: warnings.append('Proximités non précisées')
    if candidate.price_fcfa is None or candidate.area_m2 is None:
        warnings.append('Prix au m² non calculable')
    if re.search(r'\b(?:bas fond|bafon|inondable)\b', text): warnings.append('Bas-fond ou caractère inondable mentionné')
    if re.search(r'\bnon loti\w*\b', text): warnings.append('Terrain annoncé non loti')
    complete = state in {'mentionne', 'annonce_disponible'} and water in {'mentionne', 'annonce_disponible'} and electricity in {'mentionne', 'annonce_disponible'} and bool(proximities)
    return {
        'informations_completes': complete,
        'document': document, 'document_etat': state, 'document_libelle': doc_label,
        'eau_etat': water, 'electricite_etat': electricity,
        'proximites': sorted(proximities), 'atouts': strengths, 'vigilances': warnings,
        'indices': {'document':doc_score,'viabilite':(water_score+elec_score)/2,'proximite':min(len(proximities),2)/2},
    }


def land_family(candidate: SearchCandidate) -> str:
    """Évite d'utiliser des hectares agricoles comme référence d'une petite parcelle."""
    if candidate.property_type == 'maison': return 'maison'
    text = normalize_text(candidate.text)
    if (candidate.area_m2 or 0) > 2500 or re.search(r'\b(?:hectare\w*|agricole|ferme|bas fond|bafon)\b', text):
        return 'grand_terrain'
    return candidate.property_type or 'foncier'
