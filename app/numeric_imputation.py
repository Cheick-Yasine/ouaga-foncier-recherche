"""Imputation numérique déterministe par moyenne des valeurs encadrantes."""

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


def impute_surrounding_mean(
    values: Sequence[Any],
) -> tuple[list[float | None], list[str]]:
    """Impute chaque manque avec ses voisins observés les plus proches.

    Les valeurs imputées ne servent jamais de voisin à une autre imputation.
    Aux extrémités, la seule valeur observée disponible est reprise.
    """

    observed = [_to_number(value) for value in values]
    previous: list[float | None] = []
    last: float | None = None
    for value in observed:
        previous.append(last)
        if value is not None:
            last = value

    following: list[float | None] = [None] * len(observed)
    last = None
    for index in range(len(observed) - 1, -1, -1):
        following[index] = last
        if observed[index] is not None:
            last = observed[index]

    result: list[float | None] = []
    methods: list[str] = []
    for index, value in enumerate(observed):
        if value is not None:
            result.append(value)
            methods.append("observee")
        elif previous[index] is not None and following[index] is not None:
            result.append((previous[index] + following[index]) / 2)
            methods.append("moyenne_encadrement")
        elif previous[index] is not None:
            result.append(previous[index])
            methods.append("valeur_precedente")
        elif following[index] is not None:
            result.append(following[index])
            methods.append("valeur_suivante")
        else:
            result.append(None)
            methods.append("non_imputable")
    return result, methods


def _chronological_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return (
        str(row.get("premiere_collecte") or ""),
        str(row.get("id") or ""),
    )


def build_numeric_imputation_audit(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Enchaîne les phases validées puis simule l'imputation numérique."""

    features_report, features_trace = build_text_features_audit(rows)
    retained_ids = {item["id"] for item in features_trace}
    retained_rows = sorted(
        (
            row
            for row in rows
            if str(row.get("id") or "") in retained_ids
        ),
        key=_chronological_key,
    )

    original_prices = [_to_number(row.get("prix_fcfa")) for row in retained_rows]
    original_areas = [_to_number(row.get("superficie_m2")) for row in retained_rows]
    imputed_prices, price_methods = impute_surrounding_mean(original_prices)
    imputed_areas, area_methods = impute_surrounding_mean(original_areas)

    price_method_counts = Counter(price_methods)
    area_method_counts = Counter(area_methods)
    observed_targets = 0
    trace: list[dict[str, Any]] = []

    for row, original_price, original_area, price_method, area_method in zip(
        retained_rows,
        original_prices,
        original_areas,
        price_methods,
        area_methods,
        strict=True,
    ):
        price_was_missing = original_price is None
        area_was_missing = original_area is None
        target_observed = (
            not price_was_missing
            and not area_was_missing
            and original_area is not None
            and original_area > 0
        )
        if target_observed:
            observed_targets += 1
        trace.append(
            {
                "id": str(row.get("id") or ""),
                "prix_fcfa_etait_manquant": price_was_missing,
                "superficie_m2_etait_manquante": area_was_missing,
                "methode_imputation_prix": price_method,
                "methode_imputation_superficie": area_method,
                "cible_prix_m2_observee": target_observed,
                "decision": "conserver",
            }
        )

    total = len(retained_rows)
    missing_prices_before = total - price_method_counts["observee"]
    missing_areas_before = total - area_method_counts["observee"]
    missing_prices_after = sum(value is None for value in imputed_prices)
    missing_areas_after = sum(value is None for value in imputed_areas)

    report = {
        "phases": [
            *features_report["phases"],
            "Imputation des variables numériques",
        ],
        "observations_avant_imputation_numerique": total,
        "observations_supprimees_imputation_numerique": 0,
        "observations_restantes": total,
        "ordre_imputation": "premiere_collecte_puis_id",
        "methode_imputation": "moyenne_des_valeurs_observees_encadrantes",
        "prix_manquants_avant": missing_prices_before,
        "prix_manquants_apres": missing_prices_after,
        "prix_imputes": missing_prices_before - missing_prices_after,
        "methodes_prix": dict(sorted(price_method_counts.items())),
        "superficies_manquantes_avant": missing_areas_before,
        "superficies_manquantes_apres": missing_areas_after,
        "superficies_imputees": missing_areas_before - missing_areas_after,
        "methodes_superficie": dict(sorted(area_method_counts.items())),
        "cibles_prix_m2_observees": observed_targets,
        "cibles_prix_m2_non_observees": total - observed_targets,
        "regle_apprentissage": (
            "utiliser_uniquement_cible_prix_m2_observee_vraie"
        ),
        "read_only": True,
        "database_modified": False,
        "identifiers_exported": False,
        "individual_values_exported": False,
        "sensitive_text_exported": False,
        "contacts_exported": False,
    }
    return report, trace
