"""Filtrage des annonces sans prix et superficie réellement observés."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from app.text_features import build_text_features_audit


def _to_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def classify_numeric_completeness(row: Mapping[str, Any]) -> str:
    """Classe la complétude sans fabriquer de prix ni de superficie."""

    price = _to_number(row.get("prix_fcfa"))
    area = _to_number(row.get("superficie_m2"))

    if price is None and area is None:
        return "prix_et_superficie_manquants"
    if price is None:
        return "prix_manquant"
    if area is None:
        return "superficie_manquante"
    if area <= 0:
        return "superficie_non_positive"
    return "complete"


def build_numeric_completeness_audit(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Enchaîne les phases validées puis exige les deux valeurs observées."""

    features_report, features_trace = build_text_features_audit(rows)
    retained_ids = {item["id"] for item in features_trace}
    retained_rows = [
        row
        for row in rows
        if str(row.get("id") or "") in retained_ids
    ]

    status_counts: Counter[str] = Counter()
    trace: list[dict[str, Any]] = []
    retained = 0

    for row in retained_rows:
        status = classify_numeric_completeness(row)
        status_counts[status] += 1
        keep = status != "prix_et_superficie_manquants"
        if keep:
            retained += 1
        trace.append(
            {
                "id": str(row.get("id") or ""),
                "statut_completude_numerique": status,
                "prix_fcfa_observe": _to_number(row.get("prix_fcfa")) is not None,
                "superficie_m2_observee": (
                    _to_number(row.get("superficie_m2")) is not None
                    and _to_number(row.get("superficie_m2")) > 0
                ),
                "decision": (
                    "conserver"
                    if keep
                    else "exclure_base_recherche_incomplete"
                ),
            }
        )

    before = len(retained_rows)
    removed = before - retained
    report = {
        "phases": [
            *features_report["phases"],
            "Filtrage de la complétude numérique",
        ],
        "observations_avant_filtrage_numerique": before,
        "prix_seuls_manquants_conserves": status_counts["prix_manquant"],
        "superficies_seules_manquantes": status_counts[
            "superficie_manquante"
        ],
        "prix_et_superficies_manquants": status_counts[
            "prix_et_superficie_manquants"
        ],
        "superficies_non_positives": status_counts[
            "superficie_non_positive"
        ],
        "observations_supprimees_filtrage_numerique": removed,
        "observations_restantes": retained,
        "prix_ou_superficie_imputes": 0,
        "regle_recherche": (
            "exclure_uniquement_si_prix_et_superficie_manquants"
        ),
        "source_neon_rows_deleted": 0,
        "read_only": True,
        "database_modified": False,
        "identifiers_exported": False,
        "individual_values_exported": False,
        "sensitive_text_exported": False,
        "contacts_exported": False,
    }
    trace.sort(
        key=lambda item: (
            item["decision"],
            item["statut_completude_numerique"],
            item["id"],
        )
    )
    return report, trace
