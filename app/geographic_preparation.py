"""Simulation traçable de la normalisation et de la restriction géographique."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from app.deduplication import build_deduplication_audit
from app.neighborhoods import resolve_neighborhood


REFERENCE_COUNTS = {
    "observations_avant_restriction": 4_551,
    "observations_supprimees": 2_109,
    "observations_restantes": 2_442,
}


def build_geographic_preparation_audit(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Enchaîne déduplication, normalisation et restriction sans écriture."""

    deduplication_report, duplicate_trace = build_deduplication_audit(rows)
    excluded_duplicate_ids = {item["id_ecarte"] for item in duplicate_trace}
    survivors = [
        row
        for row in rows
        if str(row.get("id") or "") not in excluded_duplicate_ids
    ]

    source_counts: Counter[str] = Counter()
    zone_type_counts: Counter[str] = Counter()
    precision_counts: Counter[str] = Counter()
    trace: list[dict[str, Any]] = []
    retained = 0

    for row in survivors:
        resolution = resolve_neighborhood(
            row.get("texte_nettoye"),
            row.get("quartier_zone"),
        )
        source_counts[resolution.source] += 1
        zone_type_counts[resolution.zone_type or "non_resolu"] += 1
        precision_counts[resolution.precision] += 1
        if resolution.in_scope:
            retained += 1

        trace.append(
            {
                "id": str(row.get("id") or ""),
                "quartier_final": resolution.canonical or "",
                "source_normalisation": resolution.source,
                "nombre_quartiers_detectes": len(resolution.detected_candidates),
                "type_zone": resolution.zone_type or "",
                "precision": resolution.precision,
                "decision": "conserver" if resolution.in_scope else "exclure_hors_perimetre",
            }
        )

    before_restriction = len(survivors)
    removed = before_restriction - retained
    report = {
        "phases": ["Déduplication", "Normalisation des quartiers", "Restriction géographique"],
        "observations_chargees": len(rows),
        "observations_apres_deduplication": before_restriction,
        "doublons_certains_ecartes": len(excluded_duplicate_ids),
        "normalisation_observations_supprimees": 0,
        "observations_avant_restriction": before_restriction,
        "observations_supprimees_restriction": removed,
        "observations_restantes": retained,
        "perte_restriction_pct": round(
            (removed / before_restriction * 100) if before_restriction else 0.0,
            2,
        ),
        "sources_normalisation": dict(sorted(source_counts.items())),
        "types_zones": dict(sorted(zone_type_counts.items())),
        "niveaux_precision": dict(sorted(precision_counts.items())),
        "reference_historique": REFERENCE_COUNTS,
        "ecarts_reference": {
            "observations_avant_restriction": (
                before_restriction - REFERENCE_COUNTS["observations_avant_restriction"]
            ),
            "observations_supprimees": removed - REFERENCE_COUNTS["observations_supprimees"],
            "observations_restantes": retained - REFERENCE_COUNTS["observations_restantes"],
        },
        "deduplication": {
            "regles": deduplication_report["regles_suppression_automatique"],
            "perte_pct": deduplication_report["perte_pct"],
        },
        "read_only": True,
        "database_modified": False,
        "sensitive_text_exported": False,
        "contacts_exported": False,
    }
    trace.sort(key=lambda item: (item["decision"], item["quartier_final"], item["id"]))
    return report, trace
