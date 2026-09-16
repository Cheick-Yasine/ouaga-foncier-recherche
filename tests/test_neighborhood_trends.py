from dataclasses import replace
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
    # Cette semaine : Saaba domine les parcelles, Karpala les maisons.
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

    assert parcels[0]['nom'] == 'Saaba'
    assert parcels[0]['total'] == 4
    assert houses[0]['nom'] == 'Karpala'
    assert len(weekly['types']['tous']['quartiers']) == 5
    assert len(parcels[0]['points']) == 3  # lundi 14 -> mercredi 16
    assert sum(point['annonces'] for point in parcels[0]['points']) == 4


def test_month_and_quarter_keep_daily_granularity():
    now = datetime(2026, 9, 16, 12, tzinfo=timezone.utc)
    row = candidate('a', now, neighborhood='Saaba', days_ago=10)
    data = neighborhood_trends([row], now=now)

    monthly = data['periodes']['mensuel']['types']['tous']['quartiers'][0]
    quarterly = data['periodes']['trimestriel']['types']['tous']['quartiers'][0]
    assert len(monthly['points']) == 16
    assert len(quarterly['points']) == 78  # 1er juillet -> 16 septembre inclus
    assert sum(p['annonces'] for p in monthly['points']) == 1
    assert sum(p['annonces'] for p in quarterly['points']) == 1


def test_neighborhood_trends_endpoint_loads_enough_history(monkeypatch):
    now = datetime.now(timezone.utc)
    row = candidate('a', now, neighborhood='Saaba')
    calls = []

    def load(days, *, pool_limit, publication_days):
        calls.append((days, pool_limit, publication_days))
        return [row]

    monkeypatch.setattr('app.market_routes.load_recent_candidates', load)
    response = client.get('/market/neighborhood-trends')

    assert response.status_code == 200
    assert calls == [(None, None, 120)]
    payload = response.json()
    assert payload['granularite'] == 'jour'
    assert set(payload['periodes']) == {'hebdo', 'mensuel', 'trimestriel'}
