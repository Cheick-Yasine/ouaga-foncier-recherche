"""Tests de la préparation géographique."""

from datetime import datetime, timezone

from app.geographic_preparation import build_geographic_preparation_audit


def _row(identifier: str, text: str, fallback: str | None) -> dict[str, object]:
    return {
        "id": identifier,
        "url": f"https://facebook.com/posts/{identifier}",
        "texte_nettoye": text,
        "quartier_zone": fallback,
        "prix_fcfa": 5_000_000,
        "superficie_m2": 300,
        "premiere_collecte": datetime(2026, 8, 1, tzinfo=timezone.utc),
        "derniere_maj": datetime(2026, 8, 1, tzinfo=timezone.utc),
    }


def test_unique_text_match_has_priority() -> None:
    report, trace = build_geographic_preparation_audit(
        [_row("one", "Parcelle disponible à Saaba immédiatement", "Karpala")]
    )
    assert report["observations_restantes"] == 1
    assert trace[0]["quartier_final"] == "Saaba"
    assert trace[0]["source_normalisation"] == "texte_nettoye"


def test_fallback_is_used_when_text_has_no_known_area() -> None:
    _, trace = build_geographic_preparation_audit(
        [_row("one", "Très belle parcelle disponible immédiatement", "OUAGA2000")]
    )
    assert trace[0]["quartier_final"] == "Ouaga 2000"
    assert trace[0]["source_normalisation"] == "quartier_zone"


def test_fallback_resolves_multiple_text_matches() -> None:
    _, trace = build_geographic_preparation_audit(
        [_row("one", "Annonce entre Saaba et Karpala", "Karpala")]
    )
    assert trace[0]["nombre_quartiers_detectes"] == 2
    assert trace[0]["quartier_final"] == "Karpala"


def test_unknown_area_is_excluded_only_from_prepared_result() -> None:
    report, trace = build_geographic_preparation_audit(
        [_row("one", "Terrain situé à Bobo-Dioulasso", "Bobo-Dioulasso")]
    )
    assert report["observations_supprimees_restriction"] == 1
    assert report["observations_restantes"] == 0
    assert trace[0]["decision"] == "exclure_hors_perimetre"
    assert report["database_modified"] is False


def test_deduplication_is_applied_before_geography() -> None:
    first = _row("old", "Même annonce détaillée pour une parcelle à Saaba", "Saaba")
    second = _row("recent", "Meme annonce detaillee pour une parcelle a Saaba", "Saaba")
    second["derniere_maj"] = datetime(2026, 8, 2, tzinfo=timezone.utc)

    report, trace = build_geographic_preparation_audit([first, second])

    assert report["doublons_certains_ecartes"] == 1
    assert report["observations_avant_restriction"] == 1
    assert [item["id"] for item in trace] == ["recent"]


def test_report_does_not_export_source_text() -> None:
    report, trace = build_geographic_preparation_audit(
        [_row("one", "Annonce confidentielle à Saaba", "Saaba")]
    )
    assert "Annonce confidentielle" not in repr((report, trace))
    assert report["sensitive_text_exported"] is False
