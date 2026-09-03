"""Tests du filtrage de complétude numérique."""

from datetime import datetime, timedelta, timezone

import pytest

from app.numeric_completeness import (
    build_numeric_completeness_audit,
    classify_numeric_completeness,
)


def _row(
    identifier: str,
    *,
    price: object,
    area: object,
    day: int = 0,
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


@pytest.mark.parametrize(
    ("price", "area", "expected"),
    [
        (20_000_000, 300, "complete"),
        (None, 300, "prix_manquant"),
        (20_000_000, None, "superficie_manquante"),
        (None, None, "prix_et_superficie_manquants"),
        (20_000_000, 0, "superficie_non_positive"),
    ],
)
def test_numeric_completeness_classification(
    price: object,
    area: object,
    expected: str,
) -> None:
    assert (
        classify_numeric_completeness(
            {"prix_fcfa": price, "superficie_m2": area}
        )
        == expected
    )


def test_incomplete_rows_leave_search_base_without_imputation() -> None:
    rows = [
        _row("complete", price=20_000_000, area=300, day=0),
        _row("missing-price", price=None, area=300, day=1),
        _row("missing-area", price=20_000_000, area=None, day=2),
        _row("missing-both", price=None, area=None, day=3),
    ]
    report, trace = build_numeric_completeness_audit(rows)

    assert report["observations_avant_filtrage_numerique"] == 4
    assert report["prix_seuls_manquants"] == 1
    assert report["superficies_seules_manquantes"] == 1
    assert report["prix_et_superficies_manquants"] == 1
    assert report["observations_supprimees_filtrage_numerique"] == 3
    assert report["observations_restantes"] == 1
    assert report["prix_ou_superficie_imputes"] == 0

    by_id = {item["id"]: item for item in trace}
    assert by_id["complete"]["decision"] == "conserver"
    assert (
        by_id["missing-price"]["decision"]
        == "exclure_base_recherche_incomplete"
    )


def test_non_positive_area_is_excluded() -> None:
    report, _ = build_numeric_completeness_audit(
        [_row("zero-area", price=20_000_000, area=0)]
    )
    assert report["superficies_non_positives"] == 1
    assert report["observations_restantes"] == 0


def test_source_database_is_not_deleted() -> None:
    report, _ = build_numeric_completeness_audit(
        [_row("private-id", price=20_000_000, area=300)]
    )
    assert report["source_neon_rows_deleted"] == 0
    assert report["database_modified"] is False
    assert "private-id" not in repr(report)
