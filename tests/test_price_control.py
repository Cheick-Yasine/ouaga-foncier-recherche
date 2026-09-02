"""Tests du contrôle des prix observés."""

from datetime import datetime, timezone

from app.price_control import (
    MINIMUM_OBSERVED_PRICE_FCFA,
    build_price_control_audit,
    classify_observed_price,
)


def _row(identifier: str, price: object, area: str = "Saaba") -> dict[str, object]:
    return {
        "id": identifier,
        "url": f"https://facebook.com/posts/{identifier}",
        "texte_nettoye": f"Annonce immobilière numéro {identifier} située à {area}",
        "quartier_zone": area,
        "prix_fcfa": price,
        "superficie_m2": 300,
        "premiere_collecte": datetime(2026, 8, 1, tzinfo=timezone.utc),
        "derniere_maj": datetime(2026, 8, 1, tzinfo=timezone.utc),
    }


def test_price_classification_boundary() -> None:
    assert classify_observed_price(None) == "manquant"
    assert classify_observed_price(9_999) == "inferieur_10000"
    assert classify_observed_price(MINIMUM_OBSERVED_PRICE_FCFA) == "valide"
    assert classify_observed_price(25_000_000) == "valide"


def test_missing_price_is_retained() -> None:
    report, trace = build_price_control_audit([_row("missing", None)])
    assert report["prix_manquants_conserves"] == 1
    assert report["observations_restantes"] == 1
    assert trace[0]["decision"] == "conserver"


def test_price_below_minimum_is_excluded() -> None:
    report, trace = build_price_control_audit([_row("low", 9_999)])
    assert report["prix_inferieurs_10000_exclus"] == 1
    assert report["observations_supprimees_controle_prix"] == 1
    assert trace[0]["decision"] == "exclure_prix_incoherent"


def test_price_equal_to_minimum_is_retained() -> None:
    report, _ = build_price_control_audit([_row("boundary", 10_000)])
    assert report["prix_valides"] == 1
    assert report["observations_restantes"] == 1


def test_geography_is_applied_before_price_control() -> None:
    report, trace = build_price_control_audit(
        [_row("outside", 9_999, area="Bobo-Dioulasso")]
    )
    assert report["observations_apres_restriction_geographique"] == 0
    assert report["observations_supprimees_controle_prix"] == 0
    assert trace == []


def test_published_report_contains_only_aggregates() -> None:
    report, _ = build_price_control_audit([_row("private-id", 20_000)])
    assert "private-id" not in repr(report)
    assert report["identifiers_exported"] is False
    assert report["database_modified"] is False
