"""Extraction déterministe des caractéristiques décrites dans les annonces."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from app.villa_exclusion import build_villa_exclusion_audit


_PROXIMITY_PATTERNS = {
    "centre_sante_hopital": re.compile(
        r"\b(hopital|clinique|centre de sante|centre medical|csps|cma|dispensaire)\b"
    ),
    "ecole": re.compile(
        r"\b(ecole|lycee|college|universite|institut|etablissement scolaire)\b"
    ),
    "voie_bitumee": re.compile(
        r"\b(goudron|goudronnee?|bitume|bitumee?|voie bitumee|route bitumee)\b"
    ),
}
_ROAD_PATTERN = re.compile(
    r"\b(route|voie principale|axe principal|grande voie|rn\s*\d+)\b"
)
_WATER_PATTERN = re.compile(r"\b(eau|onea|forage)\b")
_ELECTRICITY_PATTERN = re.compile(
    r"\b(electricite|sonabel|courant|reseau electrique)\b"
)
_DOCUMENT_PATTERNS = {
    "titre_foncier": re.compile(r"\b(titre foncier|tf)\b"),
    "puh": re.compile(
        r"\b(puh|permis urbain d habiter|permis urbain de habiter)\b"
    ),
    "attestation_attribution": re.compile(
        r"\b(attestation d attribution|attestation attribution|attestation)\b"
    ),
    "apfr": re.compile(
        r"\b(apfr|attestation de possession fonciere rurale)\b"
    ),
}


def normalize_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    )
    text = text.casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def extract_proximity(*texts: Any) -> str:
    searchable = normalize_text(" ".join(str(text or "") for text in texts))
    detected = {
        label
        for label, pattern in _PROXIMITY_PATTERNS.items()
        if pattern.search(searchable)
    }

    # « route bitumée » décrit une seule caractéristique, pas deux.
    text_without_paved_phrases = _PROXIMITY_PATTERNS["voie_bitumee"].sub(
        " ", searchable
    )
    if _ROAD_PATTERN.search(text_without_paved_phrases):
        detected.add("voie_route")

    if not detected:
        return "non_precisee"
    if len(detected) > 1:
        return "plusieurs"
    return next(iter(detected))


def extract_viability(*texts: Any) -> str:
    searchable = normalize_text(" ".join(str(text or "") for text in texts))
    has_water = bool(_WATER_PATTERN.search(searchable))
    has_electricity = bool(_ELECTRICITY_PATTERN.search(searchable))
    if has_water and has_electricity:
        return "eau_et_electricite"
    if has_water:
        return "eau"
    if has_electricity:
        return "electricite"
    return "non_precisee"


def extract_document_status(structured_status: Any, *texts: Any) -> str:
    searchable = normalize_text(
        " ".join(
            [str(structured_status or ""), *(str(text or "") for text in texts)]
        )
    )
    detected = {
        label
        for label, pattern in _DOCUMENT_PATTERNS.items()
        if pattern.search(searchable)
    }
    if not detected:
        return "non_precise"
    if len(detected) > 1:
        return "plusieurs_documents"
    return next(iter(detected))


def extract_text_features(row: Mapping[str, Any]) -> dict[str, str]:
    descriptive_texts = (
        row.get("resume_court"),
        row.get("mots_cles_pertinents"),
        row.get("texte_nettoye"),
    )
    return {
        "proximite": extract_proximity(*descriptive_texts),
        "viabilite": extract_viability(*descriptive_texts),
        "statut_document_normalise": extract_document_status(
            row.get("statut_document"),
            *descriptive_texts,
        ),
    }


def build_text_features_audit(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Enchaîne les phases validées puis extrait les caractéristiques."""

    villa_report, villa_trace = build_villa_exclusion_audit(rows)
    retained_ids = {
        item["id"]
        for item in villa_trace
        if item["decision"] == "conserver"
    }
    retained_rows = [
        row
        for row in rows
        if str(row.get("id") or "") in retained_ids
    ]

    proximity_counts: Counter[str] = Counter()
    viability_counts: Counter[str] = Counter()
    document_counts: Counter[str] = Counter()
    trace: list[dict[str, Any]] = []

    for row in retained_rows:
        features = extract_text_features(row)
        proximity_counts[features["proximite"]] += 1
        viability_counts[features["viabilite"]] += 1
        document_counts[features["statut_document_normalise"]] += 1
        trace.append(
            {
                "id": str(row.get("id") or ""),
                **features,
                "decision": "conserver",
            }
        )

    total = len(retained_rows)
    report = {
        "phases": [
            *villa_report["phases"],
            "Extraction des caractéristiques textuelles",
        ],
        "observations_chargees": len(rows),
        "observations_apres_exclusion_villas": total,
        "observations_avant_extraction": total,
        "observations_supprimees_extraction": 0,
        "observations_restantes": total,
        "distribution_proximite": dict(sorted(proximity_counts.items())),
        "distribution_viabilite": dict(sorted(viability_counts.items())),
        "distribution_statut_document": dict(sorted(document_counts.items())),
        "proximite_non_precisee": proximity_counts["non_precisee"],
        "viabilite_non_precisee": viability_counts["non_precisee"],
        "document_non_precise": document_counts["non_precise"],
        "read_only": True,
        "database_modified": False,
        "identifiers_exported": False,
        "sensitive_text_exported": False,
        "contacts_exported": False,
    }
    trace.sort(key=lambda item: item["id"])
    return report, trace
