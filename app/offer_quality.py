"""Indices annoncés, sans assimiler une mention à une vérification sur place."""
from __future__ import annotations

import re
from typing import Any, TYPE_CHECKING

from app.text_features import extract_document_status

if TYPE_CHECKING:
    from app.search_engine import SearchCandidate

DOCUMENT_LABELS = {
    'apfr': 'APFR', 'puh': 'PUH', 'titre_foncier': 'Titre foncier',
    'attestation_possession': 'Attestation de possession',
    'attestation_attribution': 'Attestation / fiche d’attribution',
    'attestation_provisoire': 'Attestation provisoire',
    'attestation_cession_provisoire': 'Attestation de cession provisoire',
    'attestation_non_precisee': 'Attestation (type non précisé)',
    'plusieurs_documents': 'Plusieurs documents',
    'recepisse': 'Récépissé de dépôt', 'croquis': 'Croquis',
    'acte_vente': 'Acte de vente', 'arrete': 'Arrêté',
    'decharge': 'Décharge', 'permis_exploiter': 'Permis d’exploiter',
    'papiers_complets': 'Papiers complets',
}
PROXIMITY_LABELS = {
    'ecole': 'École à proximité', 'centre_sante_hopital': 'Centre de santé à proximité',
    'voie_bitumee': 'Voie bitumée à proximité', 'voie_route': 'Route mentionnée',
    'acces_voie_bitumee': 'Accès bitumé annoncé', 'marche': 'Marché à proximité',
}
DOC_WORD = (
    r'(?:apfr|puh|titre foncier|attestation(?: de possession(?: fonciere rurale)?)?'
    r'|attestation d attribution|attestation provisoire|attestation de cession provisoire'
    r'|fiche d attribution|certificat d attribution|papillon d attribution'
    r'|recepisse|croquis|acte de vente|arrete(?: ministeriel)?|decharge'
    r'|permis d exploiter|documents?|papiers?)'
)
ABSENT_DOC = re.compile(rf'\b(?:sans|aucun|pas de)\s+{DOC_WORD}\b|\b{DOC_WORD}\s+(?:absent|indisponible|non disponible)')
PENDING = re.compile(r'\b(?:en cours|en attente|depose\w*|demande\w*|a etablir|a fournir|a delivrer|non delivre\w*|non encore|pas encore)\b')
AVAILABLE = re.compile(r'\b(?:disponible\w*|delivre\w*|en main|en possession|obtenu\w*|remis\w*)\b')


def document_evidence(candidate: SearchCandidate) -> tuple[str | None, str, str, float]:
    """Lit uniquement le champ structuré ``statut_document`` de Neon."""

    raw = candidate.document_status
    if not raw:
        return None, "non_precise", "Document non précisé", 0.0

    document = extract_document_status(raw, "")
    if document == "non_precise":
        # Conserver la valeur structurée telle qu'elle existe en base lorsqu'elle
        # n'a pas de code interne connu, sans revenir au texte de l'annonce.
        return raw, "mentionne", f"{raw} mentionné", 0.7

    return (
        document,
        "mentionne",
        "Mentionné, disponibilité à confirmer",
        0.7,
    )


def offer_quality(candidate: SearchCandidate) -> dict[str, Any]:
    """Construit les indicateurs uniquement depuis les colonnes structurées Neon.

    Aucune information n'est ré-extraite depuis ``candidate.text``.
    """

    document, state, doc_label, doc_score = document_evidence(candidate)

    viability = candidate.viability
    water = (
        "mentionne"
        if viability in {"eau", "eau_et_electricite"}
        else "non_precise"
    )
    electricity = (
        "mentionne"
        if viability in {"electricite", "eau_et_electricite"}
        else "non_precise"
    )

    proximities = {
        value
        for value in (candidate.proximity or "").split("+")
        if value in PROXIMITY_LABELS
    }

    strengths: list[str] = []
    warnings: list[str] = []

    if state == "mentionne":
        strengths.append(DOCUMENT_LABELS.get(document, str(document)) + " mentionné")
    else:
        warnings.append(doc_label)

    if water == "mentionne":
        strengths.append("Eau mentionnée")
    if electricity == "mentionne":
        strengths.append("Électricité mentionnée")
    if water == electricity == "non_precise":
        warnings.append("Eau et électricité non précisées dans les champs structurés")

    strengths.extend(PROXIMITY_LABELS[p] for p in sorted(proximities))
    if not proximities:
        warnings.append("Proximités non précisées dans les champs structurés")

    if candidate.price_fcfa is None or candidate.area_m2 is None:
        warnings.append("Prix au m² non calculable")

    complete = (
        state == "mentionne"
        and water == "mentionne"
        and electricity == "mentionne"
        and bool(proximities)
    )

    return {
        "informations_completes": complete,
        "document": document,
        "document_etat": state,
        "document_libelle": doc_label,
        "eau_etat": water,
        "electricite_etat": electricity,
        "proximites": sorted(proximities),
        "atouts": strengths,
        "vigilances": warnings,
        "indices": {
            "document": doc_score,
            "viabilite": (
                int(water == "mentionne") + int(electricity == "mentionne")
            ) / 2,
            "proximite": min(len(proximities), 2) / 2,
        },
    }

def land_family(candidate: SearchCandidate) -> str:
    """Évite d'utiliser des hectares agricoles comme référence d'une petite parcelle."""
    if candidate.property_type == 'maison': return 'maison'
    text = normalize_text(candidate.text)
    if (candidate.area_m2 or 0) > 2500 or re.search(r'\b(?:hectare\w*|agricole|ferme|bas fond|bafon)\b', text):
        return 'grand_terrain'
    return candidate.property_type or 'foncier'
