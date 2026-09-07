"""Tests de la lecture Neon des candidats."""

from datetime import datetime, timedelta, timezone

from app.config import Settings
from app.search_repository import (
    _candidate_from_row,
    _is_prepared_candidate,
    clear_candidate_cache,
    load_recent_candidates,
)


def test_row_is_mapped_to_search_candidate() -> None:
    now = datetime(2026, 9, 3, 12, tzinfo=timezone.utc)
    candidate = _candidate_from_row(
        {
            "id": "post-1",
            "url": "https://facebook.com/posts/1",
            "date_publication": "Il y a 2 heures",
            "type_bien": "Parcelle",
            "type_bien_normalise": "parcelle",
            "quartier_zone": "Saaba",
            "superficie_m2": 300,
            "prix_fcfa": 5_000_000,
            "statut_document": "PUH",
            "resume_court": None,
            "texte_nettoye": (
                "Parcelle de 300 m2 à Saaba avec eau et PUH"
            ),
            "premiere_collecte": now - timedelta(days=2),
        },
        now=now,
    )

    assert candidate.identifier == "post-1"
    assert candidate.property_type == "parcelle"
    assert candidate.neighborhood == "Saaba"
    assert candidate.price_fcfa == 5_000_000
    assert candidate.area_m2 == 300
    assert candidate.viability == "eau"
    assert candidate.document_status == "puh"
    assert candidate.age_days == 2
    assert candidate.publication_label == "Il y a 2 heures"
    assert candidate.collected_at == "2026-09-01T12:00:00+00:00"


def test_missing_numeric_value_is_preserved() -> None:
    now = datetime(2026, 9, 3, 12, tzinfo=timezone.utc)
    candidate = _candidate_from_row(
        {
            "id": "post-2",
            "url": None,
            "date_publication": None,
            "type_bien": "Terrain",
            "type_bien_normalise": "terrain",
            "quartier_zone": "Karpala",
            "superficie_m2": 400,
            "prix_fcfa": None,
            "statut_document": None,
            "resume_court": "Terrain à Karpala",
            "texte_nettoye": None,
            "premiere_collecte": now,
        },
        now=now,
    )

    assert candidate.price_fcfa is None
    assert candidate.area_m2 == 400
    assert candidate.text == "Terrain à Karpala"


def test_price_per_hectare_uses_minimum_sale_block() -> None:
    now = datetime(2026, 9, 3, 12, tzinfo=timezone.utc)
    candidate = _candidate_from_row(
        {
            "id": "unit-hectare",
            "type_bien": "Terrain",
            "type_bien_normalise": "terrain",
            "quartier_zone": "Sankoinsé",
            "superficie_m2": 970_000,
            "prix_fcfa": 3_500_000,
            "statut_document": None,
            "resume_court": None,
            "texte_nettoye": (
                "Superficie 97 hectares. Prix 3.500.000 FCFA / hectare. "
                "Vente possible par bloc de 10 hectares minimum."
            ),
            "premiere_collecte": now,
        },
        now=now,
    )

    assert candidate.price_fcfa == 35_000_000
    assert candidate.area_m2 == 100_000
    assert candidate.pricing_note == (
        "Prix calculé pour le lot minimum de 10 hectare(s)"
    )


def test_price_per_hectare_without_minimum_uses_one_hectare() -> None:
    now = datetime(2026, 9, 3, 12, tzinfo=timezone.utc)
    candidate = _candidate_from_row(
        {
            "id": "unit-hectare-simple",
            "type_bien": "Terrain",
            "type_bien_normalise": "terrain",
            "quartier_zone": None,
            "superficie_m2": 200_000,
            "prix_fcfa": 2_250_000,
            "statut_document": None,
            "resume_court": "Terrain à 2 250 000 FCFA par hectare",
            "texte_nettoye": None,
            "premiere_collecte": now,
        },
        now=now,
    )

    assert candidate.price_fcfa == 2_250_000
    assert candidate.area_m2 == 10_000
    assert candidate.pricing_note == "Prix et superficie présentés pour 1 hectare"


def test_candidate_outside_geographic_scope_is_rejected() -> None:
    candidate = _candidate_from_row(
        {
            "id": "outside",
            "type_bien": "Terrain",
            "type_bien_normalise": "terrain",
            "quartier_zone": "Bobo-Dioulasso",
            "superficie_m2": 500,
            "prix_fcfa": 5_000_000,
            "texte_nettoye": "Terrain à Bobo-Dioulasso",
            "premiere_collecte": datetime(2026, 9, 3, tzinfo=timezone.utc),
        },
        now=datetime(2026, 9, 3, tzinfo=timezone.utc),
    )

    assert candidate.neighborhood is None
    assert _is_prepared_candidate(candidate) is False


def test_candidate_in_periphery_is_kept() -> None:
    candidate = _candidate_from_row(
        {
            "id": "periphery",
            "type_bien": "Parcelle",
            "type_bien_normalise": "parcelle",
            "quartier_zone": "Saaba",
            "superficie_m2": 300,
            "prix_fcfa": None,
            "texte_nettoye": "Parcelle à Saaba",
            "premiere_collecte": datetime(2026, 9, 3, tzinfo=timezone.utc),
        },
        now=datetime(2026, 9, 3, tzinfo=timezone.utc),
    )

    assert _is_prepared_candidate(candidate) is True


def test_unwanted_property_type_is_rejected() -> None:
    candidate = _candidate_from_row(
        {
            "id": "villa",
            "type_bien": "Villa",
            "type_bien_normalise": "villa",
            "quartier_zone": "Saaba",
            "superficie_m2": 300,
            "prix_fcfa": 20_000_000,
            "texte_nettoye": "Villa à Saaba",
            "premiere_collecte": datetime(2026, 9, 3, tzinfo=timezone.utc),
        },
        now=datetime(2026, 9, 3, tzinfo=timezone.utc),
    )

    assert _is_prepared_candidate(candidate) is False


def test_house_for_rent_is_rejected() -> None:
    candidate = _candidate_from_row(
        {
            "id": "rental-house",
            "type_bien": "Maison",
            "type_bien_normalise": "maison",
            "quartier_zone": "Karpala",
            "superficie_m2": 300,
            "prix_fcfa": 150_000,
            "texte_nettoye": "Maison à louer à Karpala, loyer 150 000 FCFA",
            "premiere_collecte": datetime(2026, 9, 3, tzinfo=timezone.utc),
        },
        now=datetime(2026, 9, 3, tzinfo=timezone.utc),
    )

    assert _is_prepared_candidate(candidate) is False


def test_house_for_sale_is_kept() -> None:
    candidate = _candidate_from_row(
        {
            "id": "sale-house",
            "type_bien": "Maison",
            "type_bien_normalise": "maison",
            "quartier_zone": "Karpala",
            "superficie_m2": 300,
            "prix_fcfa": 25_000_000,
            "texte_nettoye": "Maison à vendre à Karpala",
            "premiere_collecte": datetime(2026, 9, 3, tzinfo=timezone.utc),
        },
        now=datetime(2026, 9, 3, tzinfo=timezone.utc),
    )

    assert _is_prepared_candidate(candidate) is True


def test_recent_candidates_are_cached_between_searches(monkeypatch) -> None:
    now = datetime.now(timezone.utc)
    rows = [
        {
            "id": "cached-post",
            "url": None,
            "date_publication": None,
            "type_bien": "Parcelle",
            "type_bien_normalise": "parcelle",
            "quartier_zone": "Saaba",
            "superficie_m2": 300,
            "prix_fcfa": 5_000_000,
            "statut_document": None,
            "contacts_whatsapp": None,
            "resume_court": None,
            "texte_nettoye": "Parcelle de 300 m2 à Saaba",
            "premiere_collecte": now,
        }
    ]
    connections = 0

    class Result:
        def fetchall(self):
            return rows

    class Transaction:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def transaction(self):
            return Transaction()

        def execute(self, statement, _parameters=None):
            if "FROM public.annonces" in statement:
                return Result()
            return None

    def connect(*_args, **_kwargs):
        nonlocal connections
        connections += 1
        return Connection()

    monkeypatch.setattr(
        "app.search_repository.get_settings",
        lambda: Settings(database_url="postgresql://example.test/database"),
    )
    monkeypatch.setattr("app.search_repository.psycopg.connect", connect)
    clear_candidate_cache()

    first = load_recent_candidates()
    second = load_recent_candidates()

    assert [item.identifier for item in first] == ["cached-post"]
    assert [item.identifier for item in second] == ["cached-post"]
    assert connections == 1
    clear_candidate_cache()


def test_statistics_filters_publication_dates_before_text_analysis(monkeypatch):
    from contextlib import nullcontext
    from unittest.mock import Mock
    from app.search_repository import _candidate_cache_key

    now = datetime(2026, 9, 7, 12, tzinfo=timezone.utc)
    rows = [
        {'id': name, 'date_publication': date}
        for name, date in [
            ('recent', '2026-09-01T12:00:00Z'),
            ('boundary', (now - timedelta(days=30)).isoformat()),
            ('old', '2026-07-01T12:00:00Z'),
            ('unknown', 'Il y a un mois'),
            ('future', '2026-10-01T12:00:00Z'),
            ('missing', None),
        ]
    ]
    connection = Mock()
    connection.transaction.return_value = nullcontext()
    connection.execute.return_value.fetchall.return_value = rows
    monkeypatch.setattr('app.search_repository.psycopg.connect', lambda *a, **k: nullcontext(connection))
    mapper = Mock(side_effect=lambda row, **kwargs: row['id'])
    monkeypatch.setattr('app.search_repository._candidate_from_row', mapper)
    monkeypatch.setattr('app.search_repository._is_prepared_candidate', lambda _: True)
    settings = Settings(database_url='postgresql://example.test/database')
    assert load_recent_candidates(settings=settings, now=now, pool_limit=None, publication_days=30) == ['recent', 'boundary']
    assert mapper.call_count == 2
    query = connection.execute.call_args.args[0]
    assert 'LIMIT' not in query
    assert _candidate_cache_key('db', None, None, 30) != _candidate_cache_key('db', None, None)
    # Une recherche ordinaire conserve sa politique de date de collecte.
    assert len(load_recent_candidates(settings=settings, now=now, pool_limit=None)) == 6
