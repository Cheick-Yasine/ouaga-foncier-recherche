from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.market_stats import neighborhood_trends
from app.search_engine import SearchCandidate


client = TestClient(app)


def candidate(
    identifier,
    now,
    *,
    neighborhood='Karpala',
    property_type='parcelle',
    days_ago=0,
):
    return SearchCandidate(
        identifier,
        f'{property_type} en vente à {neighborhood}',
        neighborhood=neighborhood,
        property_type=property_type,
        price_fcfa=3_000_000,
        area_m2=300,
        publication_label=(now - timedelta(days=days_ago)).isoformat(),
    )


def test_isolated_old_dates_are_trimmed_from_the_main_activity_window():
    now = datetime(2026, 9, 18, 12, tzinfo=timezone.utc)
    rows = [
        candidate('old-1', now, neighborhood='Balkuy', days_ago=1000),
        candidate('old-2', now, neighborhood='Balkuy', days_ago=999),
    ]
    for index in range(12):
        rows.append(
            candidate(
                f'recent-{index}',
                now,
                neighborhood='Saaba',
                days_ago=index,
            )
        )

    data = neighborhood_trends(rows, now=now)

    assert data['debut'] == (now - timedelta(days=11)).date().isoformat()
    assert data['fin'] == now.date().isoformat()
    assert data['annonces_isolees_ignorees'] == 2
    assert data['types']['parcelle']['quartiers'][0]['nom'] == 'Saaba'


def test_top_five_and_property_types_use_the_retained_main_window():
    now = datetime(2026, 9, 18, 12, tzinfo=timezone.utc)
    rows = []
    for index in range(8):
        rows.append(
            candidate(
                f'saaba-{index}',
                now,
                neighborhood='Saaba',
                property_type='parcelle',
                days_ago=index,
            )
        )
    for index in range(5):
        rows.append(
            candidate(
                f'karpala-{index}',
                now,
                neighborhood='Karpala',
                property_type='maison',
                days_ago=index,
            )
        )

    data = neighborhood_trends(rows, now=now)

    assert data['granularite_source'] == 'jour'
    assert data['types']['parcelle']['quartiers'][0]['nom'] == 'Saaba'
    assert data['types']['maison']['quartiers'][0]['nom'] == 'Karpala'


def test_neighborhood_trends_endpoint_loads_full_history(monkeypatch):
    now = datetime.now(timezone.utc)
    row = candidate('a', now, neighborhood='Saaba')
    calls = []

    def load():
        calls.append(True)
        return [row]

    monkeypatch.setattr('app.market_routes.load_neighborhood_candidates', load)
    response = client.get('/market/neighborhood-trends')

    assert response.status_code == 200
    assert calls == [True]
    payload = response.json()
    assert payload['granularite_source'] == 'jour'
    assert set(payload['types']) == {'tous', 'parcelle', 'terrain', 'maison'}
