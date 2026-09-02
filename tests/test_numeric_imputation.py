"""Tests de l'imputation numérique."""

from datetime import datetime, timedelta, timezone

from app.numeric_imputation import (
    build_numeric_imputation_audit,
    impute_surrounding_mean,
)


def _row(
    identifier: str,
    *,
    price: object,
    area: object,
    day: int,
) -> dict[str, object]:
    return {
        "id": identifier,
        "url": f"https://facebook.com/posts/{identifier}",
        "texte_nettoye": f"Terrain unique {identifier} disponible à Saaba",
        "resume_court": f"Terrain {identifier} à Saaba",
        "mots_cles_pertinents": None,
        "quartier_zone": "Saaba",
        "type_bien": "terrain",
        "type_bien_normalise": "terrain",
        "prix_fcfa": price,
        "superficie_m2": area,
        "statut_document": None,
        "premiere_collecte": datetime(2026, 8, 1, tzinfo=timezone.utc)
        + timedelta(days=day),
        "derniere_maj": datetime(2026, 8, 1, tzinfo=timezone.utc)
        + timedelta(days=day),
    }


def test_surrounding_mean_uses_observed_neighbors_only() -> None:
    values, methods = impute_surrounding_mean([10, None, None, 40])
    assert values == [10, 25, 25, 40]
    assert methods == [
        "observee",
        "moyenne_encadrement",
        "moyenne_encadrement",
        "observee",
    ]


def test_edges_use_the_only_observed_neighbor() -> None:
    values, methods = impute_surrounding_mean([None, 20, None])
    assert values == [20, 20, 20]
    assert methods == ["valeur_suivante", "observee", "valeur_precedente"]


def test_all_missing_remains_unavailable() -> None:
    values, methods = impute_surrounding_mean([None, None])
    assert values == [None, None]
    assert methods == ["non_imputable", "non_imputable"]


def test_numeric_imputation_keeps_rows_and_original_flags() -> None:
    rows = [
        _row("observed", price=100_000, area=100, day=0),
        _row("missing-price", price=None, area=200, day=1),
        _row("missing-area", price=200_000, area=None, day=2),
    ]
    report, trace = build_numeric_imputation_audit(rows)

    assert report["observations_restantes"] == 3
    assert report["prix_imputes"] == 1
    assert report["superficies_imputees"] == 1
    assert report["cibles_prix_m2_observees"] == 1
    assert report["cibles_prix_m2_non_observees"] == 2

    by_id = {item["id"]: item for item in trace}
    assert by_id["missing-price"]["prix_fcfa_etait_manquant"] is True
    assert by_id["missing-price"]["cible_prix_m2_observee"] is False
    assert by_id["missing-area"]["superficie_m2_etait_manquante"] is True
    assert by_id["missing-area"]["cible_prix_m2_observee"] is False


def test_zero_area_is_not_an_observed_target() -> None:
    report, _ = build_numeric_imputation_audit(
        [_row("zero-area", price=100_000, area=0, day=0)]
    )
    assert report["cibles_prix_m2_observees"] == 0


def test_published_report_contains_only_aggregates() -> None:
    report, _ = build_numeric_imputation_audit(
        [_row("private-id", price=100_000, area=300, day=0)]
    )
    assert "private-id" not in repr(report)
    assert report["individual_values_exported"] is False
    assert report["database_modified"] is False
