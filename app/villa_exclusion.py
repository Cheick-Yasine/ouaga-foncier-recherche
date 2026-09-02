"""Exclusion déterministe des villas après le contrôle des prix."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from app.price_control import build_price_control_audit


REFERENCE_COUNTS = {
    "observations_avant": 2_441,
    "observations_supprimees": 135,
    "observations_restantes": 2_306,
}

_VILLA_TYPES = frozenset({"villa", "villas"})
_DIRECT_RETAINED_TYPES = frozenset(
    {
        "terrain",
        "terrains",
        "ferme",
        "fermes",
        "parcelle",
        "parcelles",
        "maison",
        "maisons",
    }
)
_NORMALIZED_RETAINED_TYPES = frozenset({"terrain", "parcelle", "maison"})
_VILLA_TEXT_SIGNAL = re.compile(r"\bvillas?\b", re.IGNORECASE)


def _simplify(value: Any) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(character for character in text if not unicodedata.combining(character))
    return " ".join(text.casefold().split())


def classify_villa(row: Mapping[str, Any]) -> str:
    """Retourne villa, non_villa ou a_confirmer sans transformer une villa."""

    original_type = _simplify(row.get("type_bien"))
    normalized_type = _simplify(row.get("type_bien_normalise"))

    if original_type in _VILLA_TYPES or normalized_type in _VILLA_TYPES:
        return "villa"

    # Un type structuré explicite est prioritaire sur les mots du descriptif.
    # Une parcelle destinée à construire une villa reste donc une parcelle.
    if (
        original_type in _DIRECT_RETAINED_TYPES
        or normalized_type in _NORMALIZED_RETAINED_TYPES
    ):
        return "non_villa"

    searchable_text = _simplify(
        " ".join(
            str(row.get(field) or "")
            for field in ("resume_court", "texte_nettoye")
        )
    )
    if _VILLA_TEXT_SIGNAL.search(searchable_text):
        return "villa"

    return "a_confirmer"


def build_villa_exclusion_audit(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Enchaîne les phases validées et simule l'exclusion des villas."""

    price_report, price_trace = build_price_control_audit(rows)
    price_retained_ids = {
        item["id"]
        for item in price_trace
        if item["decision"] == "conserver"
    }
    retained_after_price = [
        row
        for row in rows
        if str(row.get("id") or "") in price_retained_ids
    ]

    status_counts: Counter[str] = Counter()
    trace: list[dict[str, Any]] = []
    retained = 0

    for row in retained_after_price:
        status = classify_villa(row)
        status_counts[status] += 1
        keep = status != "villa"
        if keep:
            retained += 1
        trace.append(
            {
                "id": str(row.get("id") or ""),
                "statut_villa": status,
                "decision": "conserver" if keep else "exclure_villa",
            }
        )

    before = len(retained_after_price)
    removed = before - retained
    report = {
        "phases": [
            *price_report["phases"],
            "Exclusion du type villa",
        ],
        "observations_chargees": len(rows),
        "observations_apres_deduplication": price_report[
            "observations_apres_deduplication"
        ],
        "observations_apres_restriction_geographique": price_report[
            "observations_apres_restriction_geographique"
        ],
        "observations_apres_controle_prix": before,
        "observations_avant_exclusion_villas": before,
        "villas_exclues": status_counts["villa"],
        "non_villas_conservees": status_counts["non_villa"],
        "types_a_confirmer_conserves": status_counts["a_confirmer"],
        "observations_supprimees_exclusion_villas": removed,
        "observations_restantes": retained,
        "regle_villa": "exclue_sans_conversion_en_maison",
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
    trace.sort(key=lambda item: (item["decision"], item["statut_villa"], item["id"]))
    return report, trace
