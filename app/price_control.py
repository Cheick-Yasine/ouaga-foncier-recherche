"""Contrôle déterministe des prix après préparation géographique."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

from app.geographic_preparation import build_geographic_preparation_audit


MINIMUM_OBSERVED_PRICE_FCFA = 10_000
REFERENCE_COUNTS = {
    "observations_avant": 2_442,
    "observations_supprimees": 1,
    "observations_restantes": 2_441,
}


def classify_observed_price(value: Any) -> str:
    """Classe un prix comme manquant, valide, trop faible ou invalide."""

    if value is None or (isinstance(value, str) and not value.strip()):
        return "manquant"
    if isinstance(value, bool):
        return "invalide"
    try:
        price = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return "invalide"
    if not price.is_finite():
        return "invalide"
    if price < MINIMUM_OBSERVED_PRICE_FCFA:
        return "inferieur_10000"
    return "valide"


def build_price_control_audit(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Enchaîne les phases validées puis contrôle les prix sans écriture."""

    geography_report, geography_trace = build_geographic_preparation_audit(rows)
    geographically_retained_ids = {
        item["id"]
        for item in geography_trace
        if item["decision"] == "conserver"
    }
    retained_rows = [
        row
        for row in rows
        if str(row.get("id") or "") in geographically_retained_ids
    ]

    status_counts: Counter[str] = Counter()
    trace: list[dict[str, Any]] = []
    retained = 0
    for row in retained_rows:
        status = classify_observed_price(row.get("prix_fcfa"))
        status_counts[status] += 1
        keep = status in {"valide", "manquant"}
        if keep:
            retained += 1
        trace.append(
            {
                "id": str(row.get("id") or ""),
                "statut_prix": status,
                "prix_etait_manquant": status == "manquant",
                "decision": "conserver" if keep else "exclure_prix_incoherent",
            }
        )

    before = len(retained_rows)
    removed = before - retained
    report = {
        "phases": [
            "Déduplication",
            "Normalisation des quartiers",
            "Restriction géographique",
            "Contrôle des prix observés",
        ],
        "observations_chargees": len(rows),
        "observations_apres_deduplication": geography_report[
            "observations_apres_deduplication"
        ],
        "observations_apres_restriction_geographique": before,
        "observations_avant_controle_prix": before,
        "prix_valides": status_counts["valide"],
        "prix_manquants_conserves": status_counts["manquant"],
        "prix_inferieurs_10000_exclus": status_counts["inferieur_10000"],
        "prix_invalides_exclus": status_counts["invalide"],
        "observations_supprimees_controle_prix": removed,
        "observations_restantes": retained,
        "seuil_minimum_fcfa": MINIMUM_OBSERVED_PRICE_FCFA,
        "reference_historique": REFERENCE_COUNTS,
        "ecarts_reference": {
            "observations_avant": before - REFERENCE_COUNTS["observations_avant"],
            "observations_supprimees": removed
            - REFERENCE_COUNTS["observations_supprimees"],
            "observations_restantes": retained
            - REFERENCE_COUNTS["observations_restantes"],
        },
        "read_only": True,
        "database_modified": False,
        "identifiers_exported": False,
        "sensitive_text_exported": False,
        "contacts_exported": False,
    }
    trace.sort(key=lambda item: (item["decision"], item["statut_prix"], item["id"]))
    return report, trace
