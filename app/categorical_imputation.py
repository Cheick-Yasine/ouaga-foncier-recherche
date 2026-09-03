"""Imputation catégorielle explicite des valeurs absentes."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from app.geographic_preparation import build_geographic_preparation_audit
from app.normalization import normalize_property_type
from app.numeric_completeness import build_numeric_completeness_audit
from app.text_features import build_text_features_audit


MISSING_CATEGORY = "manquante"


def impute_category(value: Any) -> str:
    """Transforme uniquement une valeur absente ou vide en « manquante »."""

    if value is None:
        return MISSING_CATEGORY
    rendered = str(value).strip()
    return rendered if rendered else MISSING_CATEGORY


def build_categorical_imputation_audit(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Enchaîne les phases validées puis impute les catégories absentes."""

    completeness_report, completeness_trace = build_numeric_completeness_audit(rows)
    retained_ids = {
        item["id"]
        for item in completeness_trace
        if item["decision"] == "conserver"
    }

    _, geography_trace = build_geographic_preparation_audit(rows)
    neighborhoods = {
        item["id"]: item["quartier_final"]
        for item in geography_trace
        if item["decision"] == "conserver"
    }

    _, features_trace = build_text_features_audit(rows)
    features_by_id = {item["id"]: item for item in features_trace}

    missing_before: Counter[str] = Counter()
    missing_after: Counter[str] = Counter()
    type_counts: Counter[str] = Counter()
    proximity_counts: Counter[str] = Counter()
    viability_counts: Counter[str] = Counter()
    document_counts: Counter[str] = Counter()
    trace: list[dict[str, Any]] = []

    for row in rows:
        identifier = str(row.get("id") or "")
        if identifier not in retained_ids:
            continue

        features = features_by_id.get(identifier, {})
        raw_values = {
            "quartier_final": neighborhoods.get(identifier),
            "type_bien_normalise": normalize_property_type(
                row.get("type_bien"),
                row.get("resume_court"),
                row.get("texte_nettoye"),
            ),
            "proximite": features.get("proximite"),
            "viabilite": features.get("viabilite"),
            "statut_document": features.get("statut_document_normalise"),
        }
        final_values: dict[str, str] = {}
        for field, value in raw_values.items():
            if value is None or not str(value).strip():
                missing_before[field] += 1
            final_values[field] = impute_category(value)
            if final_values[field] == MISSING_CATEGORY:
                missing_after[field] += 1

        type_counts[final_values["type_bien_normalise"]] += 1
        proximity_counts[final_values["proximite"]] += 1
        viability_counts[final_values["viabilite"]] += 1
        document_counts[final_values["statut_document"]] += 1
        trace.append(
            {
                "id": identifier,
                **final_values,
                "decision": "conserver",
            }
        )

    fields = (
        "quartier_final",
        "type_bien_normalise",
        "proximite",
        "viabilite",
        "statut_document",
    )
    total = len(trace)
    report = {
        "phases": [
            *completeness_report["phases"],
            "Imputation des variables catégorielles",
        ],
        "observations_avant_imputation_categorielle": total,
        "observations_supprimees_imputation_categorielle": 0,
        "observations_restantes": total,
        "categorie_imputation": MISSING_CATEGORY,
        "valeurs_manquantes_avant": {
            field: missing_before[field] for field in fields
        },
        "valeurs_manquantes_apres": {
            field: missing_after[field] for field in fields
        },
        "valeurs_converties_en_manquante": {
            field: missing_before[field] for field in fields
        },
        "nombre_quartiers_finaux": len(
            {
                item["quartier_final"]
                for item in trace
                if item["quartier_final"] != MISSING_CATEGORY
            }
        ),
        "distribution_type_bien": dict(sorted(type_counts.items())),
        "distribution_proximite": dict(sorted(proximity_counts.items())),
        "distribution_viabilite": dict(sorted(viability_counts.items())),
        "distribution_statut_document": dict(sorted(document_counts.items())),
        "non_precisee_reste_distincte_de_manquante": True,
        "read_only": True,
        "database_modified": False,
        "identifiers_exported": False,
        "sensitive_text_exported": False,
        "contacts_exported": False,
    }
    trace.sort(key=lambda item: item["id"])
    return report, trace
