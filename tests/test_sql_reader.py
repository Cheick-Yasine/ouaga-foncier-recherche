"""SQL authorization and execution against a disposable PostgreSQL database."""
import os
from datetime import datetime, timezone

import pytest
import psycopg

from app.config import Settings
from app.sql_reader import validate_select, query_annonces, read_references, SQLReadError
from app.public_references import public_announcement_id


@pytest.mark.parametrize('sql', [
    'DELETE FROM public.annonces',
    'SELECT id FROM annonces; DROP TABLE annonces',
    'WITH x AS (DELETE FROM annonces RETURNING id) SELECT id FROM x',
    'SELECT id FROM users', 'SELECT id FROM pg_catalog.pg_class',
    'SELECT id FROM other.annonces',
    'SELECT id FROM annonces WHERE EXISTS (SELECT 1 FROM users)',
    'SELECT id FROM annonces UNION SELECT id FROM users',
    'SELECT id INTO sauvegarde FROM annonces',
    'SELECT id FROM annonces FOR UPDATE',
    'SELECT id FROM annonces WHERE pg_sleep(100) IS NULL',
    "SELECT id FROM annonces ORDER BY set_config('search_path','public',false)",
    "SELECT id FROM annonces WHERE texte_nettoye::regclass IS NOT NULL",
    'SELECT id FROM annonces a JOIN annonces b ON a.id=b.id',
    'SELECT contacts_whatsapp FROM annonces',
    "SELECT id FROM annonces WHERE contacts_whatsapp LIKE '%'",
    'SELECT * FROM annonces', 'SELECT id FROM annonces OFFSET 100000',
    'SELECT id FROM annonces LIMIT 100000', 'SELECT id FROM annonces LIMIT -1',
    'SELECT id FROM annonces TABLESAMPLE SYSTEM (10)',
])
def test_rejects_unauthorized_sql(sql):
    with pytest.raises(SQLReadError):
        validate_select(sql)


def test_accepts_model_filters_and_bounds_results():
    sql = validate_select("SELECT id FROM annonces WHERE quartier_zone ILIKE '%saaba%' AND prix_fcfa <= 6000000 ORDER BY prix_fcfa / NULLIF(superficie_m2, 0)")
    assert 'public.annonces' in sql
    assert 'LIMIT 100' in sql
    assert '6000000' in sql


def test_sql_words_inside_text_are_data():
    assert 'SELECT' in validate_select("SELECT id FROM annonces WHERE texte_nettoye = 'DROP TABLE users;'")


@pytest.fixture
def postgres_settings():
    url = os.environ.get('TEST_SQL_DATABASE_URL')
    if not url:
        pytest.skip('Disposable PostgreSQL is provided by CI')
    with psycopg.connect(url, autocommit=True) as db:
        db.execute('DROP TABLE IF EXISTS public.annonces')
        db.execute('''CREATE TABLE public.annonces (
            id text PRIMARY KEY, url text, date_publication text,
            premiere_collecte timestamptz, type_bien text, type_bien_normalise text,
            quartier_zone text, superficie_m2 numeric, prix_fcfa numeric,
            statut_document text, resume_court text, texte_nettoye text)''')
        for identifier, price, zone in [('a', 5000000, 'Saaba'), ('b', 8000000, 'Saaba'), ('c', 3000000, 'Karpala')]:
            db.execute('''INSERT INTO public.annonces
                (id, prix_fcfa, superficie_m2, quartier_zone, texte_nettoye, premiere_collecte)
                VALUES (%s,%s,300,%s,'Parcelle en vente',%s)''',
                (identifier, price, zone, datetime.now(timezone.utc)))
    return Settings(database_url=url)


def test_executes_gpt_select_and_preserves_its_order(postgres_settings):
    rows = query_annonces('SELECT id FROM annonces ORDER BY prix_fcfa DESC LIMIT 2', settings=postgres_settings)
    assert [r['id'] for r in rows] == ['b', 'a']
    # No hidden budget or zone filter, and no Python reranking.
    rows = query_annonces("SELECT id FROM annonces WHERE quartier_zone = 'Saaba' AND prix_fcfa <= 6000000", settings=postgres_settings)
    assert [r['id'] for r in rows] == ['a']
    refs = [public_announcement_id('c'), public_announcement_id('a')]
    assert [r['id'] for r in read_references(refs, settings=postgres_settings)] == ['c', 'a']


def test_rejected_write_leaves_table_intact(postgres_settings):
    with pytest.raises(SQLReadError):
        query_annonces('DELETE FROM annonces', settings=postgres_settings)
    assert len(query_annonces('SELECT id FROM annonces', settings=postgres_settings)) == 3
