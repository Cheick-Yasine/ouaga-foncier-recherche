from datetime import datetime, timezone

import pytest

from app.prepared_data import prepare_publication, prepare_rows


def source(text, **kwargs):
    return dict(id='source-1', texte_nettoye=text, type_bien='terrain',
                quartier_zone='Saaba', prix_fcfa=3500000, superficie_m2=300,
                premiere_collecte=datetime.now(timezone.utc), **kwargs)


@pytest.mark.parametrize('text,reason', [
    ('Terrain en location à Saaba', 'location_demande_ou_indisponible'),
    ('Terrain en vente ou location à Saaba', 'location_demande_ou_indisponible'),
    ('Je cherche un terrain à Saaba', 'location_demande_ou_indisponible'),
    ('Terrain déjà vendu à Saaba', 'location_demande_ou_indisponible'),
    ('Terrain à Saaba', 'vente_non_confirmee'),
    ('Terrain en vente à Bobo-Dioulasso', 'hors_perimetre'),
    ('Villa en vente à Saaba', 'type_hors_perimetre_ou_ambigu'),
    ('Terrain en vente à Saaba superficie 300m² prix 3 millions 500', 'montant_compose_a_verifier'),
])
def test_excludes_and_explains(text, reason):
    lots, actual = prepare_publication(source(text))
    assert lots == []
    assert actual == reason


def test_splits_explicit_lots_without_mixing_their_prices():
    row = source('Terrain en vente à Saaba. Superficie 160m² prix 1.250.000 FCFA. Superficie 140m² prix 950.000 FCFA.')
    lots, reason = prepare_publication(row)
    assert reason == 'conserve'
    assert [(r['superficie_m2'],r['prix_fcfa']) for r in lots] == [(160,1250000),(140,950000)]
    assert '950.000' not in lots[0]['texte_nettoye']
    assert '1.250.000' not in lots[1]['texte_nettoye']
    assert lots[0]['source_id'] == lots[1]['source_id'] == row['id']
    assert lots[0]['id'] != lots[1]['id']
    assert row['prix_fcfa'] == 3500000


def test_normalizes_total_and_keeps_missing_values():
    lots, _ = prepare_publication(source('Terrain en vente à Saaba 2 hectares prix 3 millions par hectare'))
    assert lots[0]['prix_fcfa'] == 6000000
    assert lots[0]['superficie_m2'] == 20000
    row = source('Terrain en vente à Saaba')
    row['superficie_m2'] = None
    lots, _ = prepare_publication(row)
    assert lots[0]['superficie_m2'] is None
    assert lots[0]['document_etat'] == 'non_precise'
    row['prix_fcfa'] = None
    assert prepare_publication(row)[1] == 'prix_et_superficie_absents'


def test_does_not_deduplicate_different_publications_with_same_features():
    row = source('Terrain en vente à Saaba')
    lots, audit, report = prepare_rows([row, dict(row, id='another')])
    assert len(lots) == len(audit) == 2
    assert report['decisions'] == {'conserve': 2}


def test_atomic_refresh_keeps_raw_data_and_preserves_catalogue_on_failure():
    import os
    import psycopg
    from psycopg.rows import dict_row
    from scripts.prepare_annonces import refresh
    url = os.environ.get('TEST_SQL_DATABASE_URL')
    if not url:
        pytest.skip('Disposable PostgreSQL required')
    with psycopg.connect(url, autocommit=True, row_factory=dict_row) as db:
        db.execute('DROP TABLE IF EXISTS public.annonces_preparees')
        db.execute('DROP TABLE IF EXISTS public.annonces')
        db.execute('''CREATE TABLE public.annonces (id text PRIMARY KEY,
            texte_nettoye text, type_bien text, quartier_zone text,
            prix_fcfa numeric, superficie_m2 numeric)''')
        db.execute("INSERT INTO public.annonces VALUES ('a','Terrain en vente à Saaba','terrain','Saaba',3000000,300), ('b','Terrain en location à Saaba','terrain','Saaba',50000,300)")
        assert refresh(db)['lots_prepares'] == 1
        assert db.execute("SELECT to_regclass('public.annonces_preparees') AS t").fetchone()['t'] is None
        assert refresh(db, True)['lots_prepares'] == 1
        assert db.execute('SELECT count(*) AS n FROM public.annonces').fetchone()['n'] == 2
        assert db.execute('SELECT id FROM public.annonces_preparees').fetchone()['id'] == 'a'
        assert db.execute("SELECT motif FROM public.annonces_preparation_audit WHERE source_id='b'").fetchone()['motif'] == 'location_demande_ou_indisponible'
        db.execute("UPDATE public.annonces SET texte_nettoye='Terrain en location à Saaba'")
        with pytest.raises(ValueError):
            refresh(db, True)
        assert db.execute('SELECT id FROM public.annonces_preparees').fetchone()['id'] == 'a'
