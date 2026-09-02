"""Tests de l'exclusion des villas."""

from datetime import datetime, timezone

from app.villa_exclusion import (
    build_villa_exclusion_audit,
    classify_villa,
)


def _row(
    identifier: str,
    *,
    original_type: str | None,
    normalized_type: str | None = None,
    text: str = "Annonce immobilière disponible à Saaba",
    price: object = 20_000_000,
) -> dict[str, object]:
    return {
        "id": identifier,
        "url": f"https://facebook.com/posts/{identifier}",
        "texte_nettoye": f"{text} référence {identifier}",
        "resume_court": text,
        "quartier_zone": "Saaba",
        "type_bien": original_type,
        "type_bien_normalise": normalized_type,
        "prix_fcfa": price,
        "superficie_m2": 300,
        "premiere_collecte": datetime(2026, 8, 1, tzinfo=timezone.utc),
        "derniere_maj": datetime(2026, 8, 1, tzinfo=timezone.utc),
    }


def test_direct_villa_is_excluded() -> None:
    assert classify_villa(_row("villa", original_type="Villa")) == "villa"


def test_villa_is_never_converted_to_house() -> None:
    report, trace = build_villa_exclusion_audit(
        [_row("villa", original_type="villa")]
    )
    assert report["villas_exclues"] == 1
    assert report["observations_restantes"] == 0
    assert trace[0]["decision"] == "exclure_villa"
    assert "maison" not in trace[0].values()


def test_untyped_villa_detected_in_text_is_excluded() -> None:
    row = _row(
        "text-villa",
        original_type="autre",
        text="Belle villa disponible à Saaba",
    )
    assert classify_villa(row) == "villa"


def test_explicit_parcel_mentioning_future_villa_is_retained() -> None:
    row = _row(
        "parcel",
        original_type="parcelle",
        normalized_type="parcelle",
        text="Parcelle idéale pour construire une villa à Saaba",
    )
    assert classify_villa(row) == "non_villa"


def test_unknown_non_villa_is_retained_for_later_review() -> None:
    report, _ = build_villa_exclusion_audit(
        [_row("unknown", original_type="autre", text="Bien disponible à Saaba")]
    )
    assert report["types_a_confirmer_conserves"] == 1
    assert report["observations_restantes"] == 1


def test_price_control_runs_before_villa_exclusion() -> None:
    report, trace = build_villa_exclusion_audit(
        [_row("low-villa", original_type="villa", price=9_999)]
    )
    assert report["observations_apres_controle_prix"] == 0
    assert report["villas_exclues"] == 0
    assert trace == []


def test_published_report_contains_only_aggregates() -> None:
    report, _ = build_villa_exclusion_audit(
        [_row("private-id", original_type="terrain")]
    )
    assert "private-id" not in repr(report)
    assert report["identifiers_exported"] is False
    assert report["database_modified"] is False
