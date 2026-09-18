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


def test_top_five_uses_the_full_database_history():
    now = datetime(2026, 9, 18, 12, tzinfo=timezone.utc)
    rows = []

    # Saaba domine grâce à des annonces anciennes (> 90 jours) :
    # elles doivent désormais compter dans le Top 5.
    for index in range(6):
        rows.append(
            candidate(
                f'saaba-old-{index}',
                now,
                neighborhood='Saaba',
                days_ago=180 + index,
            )
        )
    for index in range(4):
        rows.append(
            candidate(
                f'karpala-recent-{index}',
                now,
                neighborhood='Karpala',
                days_ago=index,
            )
        )
    for index, name in enumerate(
        ['Balkuy', 'Bassinko', 'Kamboinsin', 'Tampouy', 'Zagtouli']
    ):
        rows.append(
            candidate(
                f'other-{index}',
                now,
                neighborhood=name,
                days_ago=30 + index,
            )
        )

    data = neighborhood_trends(rows, now=now)
    parcels = data['types']['parcelle']['quartiers']

    assert data['granularite_source'] == 'jour'
    assert parcels[0]['nom'] == 'Saaba'
    assert parcels[0]['total'] == 6
    assert len(data['types']['tous']['quartiers']) == 5

    # La série quotidienne couvre bien l'historique complet, pas 90 jours.
    assert data['debut'] <= (now - timedelta(days=185)).date().isoformat()
    assert data['fin'] == now.date().isoformat()
    assert sum(point['annonces'] for point in parcels[0]['points']) == 6


def test_property_type_filter_keeps_its_own_full_history_top_five():
    now = datetime(2026, 9, 18, 12, tzinfo=timezone.utc)
    rows = [
        candidate('p1', now, neighborhood='Saaba', property_type='parcelle', days_ago=200),
        candidate('p2', now, neighborhood='Saaba', property_type='parcelle', days_ago=100),
        candidate('m1', now, neighborhood='Karpala', property_type='maison', days_ago=150),
        candidate('m2', now, neighborhood='Karpala', property_type='maison', days_ago=20),
        candidate('m3', now, neighborhood='Karpala', property_type='maison', days_ago=2),
    ]

    data = neighborhood_trends(rows, now=now)

    parcels = data['types']['parcelle']['quartiers']
    houses = data['types']['maison']['quartiers']
    assert parcels[0]['nom'] == 'Saaba'
    assert parcels[0]['total'] == 2
    assert houses[0]['nom'] == 'Karpala'
    assert houses[0]['total'] == 3


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
