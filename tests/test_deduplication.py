"""Tests de la déduplication traçable."""

from datetime import datetime, timezone

import pytest

from app.deduplication import (
    build_deduplication_audit,
    characteristic_key,
    normalized_text_key,
    normalized_url_key,
)


def _row(identifier: str, **updates: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": identifier,
        "url": f"https://facebook.com/posts/{identifier}",
        "texte_nettoye": f"Annonce immobilière suffisamment longue numéro {identifier}",
        "quartier_zone": "Saaba",
        "prix_fcfa": 5_000_000,
        "superficie_m2": 300,
        "premiere_collecte": datetime(2026, 8, 1, tzinfo=timezone.utc),
        "derniere_maj": datetime(2026, 8, 1, tzinfo=timezone.utc),
    }
    row.update(updates)
    return row


def test_text_and_url_normalization() -> None:
    assert normalized_text_key("Parcelle à SAABA !") == "parcelle a saaba"
    assert normalized_url_key("https://FACEBOOK.com/posts/1/?tracking=x") == (
        "https://facebook.com/posts/1"
    )


def test_latest_republication_is_kept() -> None:
    old = _row(
        "old",
        url="https://facebook.com/posts/shared?first=1",
        texte_nettoye="Même publication foncière détaillée à Saaba",
        derniere_maj=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )
    recent = _row(
        "recent",
        url="https://facebook.com/posts/shared?second=2",
        texte_nettoye="Meme publication fonciere detaillee a Saaba",
        derniere_maj=datetime(2026, 8, 3, tzinfo=timezone.utc),
    )

    report, trace = build_deduplication_audit([old, recent])

    assert report["observations_supprimees_simulees"] == 1
    assert report["observations_restantes_simulees"] == 1
    assert trace[0]["id_conserve"] == "recent"
    assert trace[0]["id_ecarte"] == "old"
    assert "same_url" in trace[0]["motifs"]
    assert "same_normalized_text" in trace[0]["motifs"]


def test_same_characteristics_are_candidates_not_deleted() -> None:
    first = _row("one")
    second = _row("two")

    report, trace = build_deduplication_audit([first, second])

    assert trace == []
    assert report["observations_restantes_simulees"] == 2
    assert report["candidats_caracteristiques"] == 1
    assert report["candidate_clusters"][0]["decision"] == "review_required"


def test_missing_characteristics_do_not_form_candidate_key() -> None:
    assert characteristic_key(_row("one", superficie_m2=None)) is None
    assert characteristic_key(_row("two", quartier_zone="")) is None


def test_report_does_not_export_text_or_contacts() -> None:
    report, trace = build_deduplication_audit([_row("one")])
    rendered = repr((report, trace))
    assert "Annonce immobilière" not in rendered
    assert report["sensitive_text_exported"] is False
    assert report["contacts_exported"] is False


def test_empty_or_repeated_identifier_is_rejected() -> None:
    with pytest.raises(ValueError):
        build_deduplication_audit([_row("")])
    with pytest.raises(ValueError):
        build_deduplication_audit([_row("same"), _row("same")])
