from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.market_stats import neighborhood_trends
from app.search_engine import SearchCandidate


client = TestClient(app)


def candidate(identifier, now, *, neighborhood='Karpala', property_type='parcelle', days_ago=0):
    return SearchCandidate(
        identifier,
        f'{property_type} en vente à {neighborhood}',
        neighborhood=neighborhood,
        property_type=property_type,
        price_fcfa=3_000_000,
        area_m2=300,
        publication_label=(now - timedelta(days=days_ago)).isoformat(),
    )


def test_top_five_is_recomputed_by_period_and_property_type():
    now = datetime(2026, 9, 16, 12, tzinfo=timezone.utc)
    rows = []
    for index in range(4):
        rows.append(candidate(f'saaba-{index}', now, neighborhood='Saaba', days_ago=index % 3))
    for index in range(3):
        rows.append(candidate(f'karpala-house-{index}', now, neighborhood='Karpala', property_type='maison', days_ago=index % 2))
    for index, name in enumerate(['Balkuy', 'Bassinko', 'Kamboinsin', 'Tampouy', 'Zagtouli']):
        rows.append(candidate(f'other-{index}', now, neighborhood=name, days_ago=1))

    data = neighborhood_trends(rows, now=now)
    weekly = data['periodes']['hebdo']
    parcels = weekly['types']['parcelle']['quartiers']
    houses = weekly['types']['maison']['quartiers']

    assert weekly['granularite'] == 'jour'
    assert parcels[0]['nom'] == 'Saaba'
    assert parcels[0]['total'] == 4
    assert houses[0]['nom'] == 'Karpala'
    assert len(weekly['types']['tous']['quartiers']) == 5
    assert len(parcels[0]['points']) == 3  # lundi 14 -> mercredi 16
    assert sum(point['annonces'] for point in parcels[0]['points']) == 4


def test_month_is_weekly_and_quarter_is_monthly():
    now = datetime(2026, 9, 16, 12, tzinfo=timezone.utc)
    rows = [
        candidate('sept', now, neighborhood='Saaba', days_ago=10),
        candidate('aug', now, neighborhood='Saaba', days_ago=35),
        candidate('jul', now, neighborhood='Saaba', days_ago=70),
    ]
    data = neighborhood_trends(rows, now=now)

    monthly = data['periodes']['mensuel']
    quarterly = data['periodes']['trimestriel']
    assert monthly['granularite'] == 'semaine'
    assert quarterly['granularite'] == 'mois'

    monthly_points = monthly['types']['tous']['quartiers'][0]['points']
    quarterly_points = quarterly['types']['tous']['quartiers'][0]['points']
    assert len(monthly_points) == 3  # 1-7, 8-14, 15-16 septembre
    assert len(quarterly_points) == 3  # juillet, août, septembre
    assert sum(p['annonces'] for p in monthly_points) == 1
    assert sum(p['annonces'] for p in quarterly_points) == 3


def test_neighborhood_trends_endpoint_loads_enough_history(monkeypatch):
    now = datetime.now(timezone.utc)
    row = candidate('a', now, neighborhood='Saaba')
    calls = []

    def load(*, publication_days):
        calls.append(publication_days)
        return [row]

    monkeypatch.setattr('app.market_routes.load_neighborhood_candidates', load)
    response = client.get('/market/neighborhood-trends')

    assert response.status_code == 200
    assert calls == [95]
    payload = response.json()
    assert set(payload['periodes']) == {'hebdo', 'mensuel', 'trimestriel'}
    assert payload['periodes']['hebdo']['granularite'] == 'jour'
    assert payload['periodes']['mensuel']['granularite'] == 'semaine'
    assert payload['periodes']['trimestriel']['granularite'] == 'mois'
