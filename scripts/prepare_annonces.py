"""Audit by default; --apply atomically refreshes derived tables only."""
import argparse
import json
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.config import get_settings
from app.prepared_data import prepare_rows


SCHEMA = '''CREATE TABLE IF NOT EXISTS public.annonces_preparees (
    id text PRIMARY KEY, source_id text NOT NULL, lot_numero integer NOT NULL,
    url text, date_publication text, premiere_collecte timestamptz,
    type_bien text, type_bien_normalise text NOT NULL CHECK (type_bien_normalise IN ('terrain','parcelle','maison')),
    quartier_zone text NOT NULL, superficie_m2 double precision, prix_fcfa double precision,
    statut_document text, resume_court text, texte_nettoye text, contacts_whatsapp text,
    document_etat text, eau_etat text, electricite_etat text,
    dans_ouagadougou boolean NOT NULL, qualite_preparee jsonb NOT NULL,
    base_prix text, preparation_version integer NOT NULL,
    preparee_le timestamptz NOT NULL DEFAULT now(),
    CHECK (prix_fcfa IS NULL OR prix_fcfa >= 10000),
    CHECK (superficie_m2 IS NULL OR superficie_m2 > 0),
    CHECK (prix_fcfa IS NOT NULL OR superficie_m2 IS NOT NULL)
)'''
COLUMNS = ('id','source_id','lot_numero','url','date_publication','premiere_collecte',
           'type_bien','type_bien_normalise','quartier_zone','superficie_m2','prix_fcfa',
           'statut_document','resume_court','texte_nettoye','contacts_whatsapp',
           'document_etat','eau_etat','electricite_etat','dans_ouagadougou',
           'qualite_preparee','base_prix','preparation_version')


def refresh(connection, apply=False):
    with connection.transaction():
        connection.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
        connection.execute("SET LOCAL statement_timeout = '120s'")
        connection.execute("SET LOCAL lock_timeout = '5s'")
        if apply:
            connection.execute('SELECT pg_advisory_xact_lock(729615031)')
        sources = connection.execute('SELECT * FROM public.annonces').fetchall()
        rows, audit, report = prepare_rows(sources)
        report['applique'] = apply
        if not apply:
            return report
        # An unexpected empty extraction must never empty a working catalogue.
        if not rows:
            raise ValueError('Aucune annonce préparée : bascule annulée, consulter le rapport en simulation.')
        connection.execute(SCHEMA)
        connection.execute('''CREATE TABLE IF NOT EXISTS public.annonces_preparation_audit (
            source_id text PRIMARY KEY, motif text NOT NULL, lots integer NOT NULL,
            verifie_le timestamptz NOT NULL DEFAULT now())''')
        connection.execute('''CREATE TABLE IF NOT EXISTS public.annonces_preparation_runs (
            termine_le timestamptz NOT NULL DEFAULT now(), rapport jsonb NOT NULL)''')
        connection.execute('DELETE FROM public.annonces_preparees')
        with connection.cursor() as cursor:
            cursor.executemany('INSERT INTO public.annonces_preparees (' + ','.join(COLUMNS) + ') VALUES (' + ','.join(['%s']*len(COLUMNS)) + ')',
                [tuple(Jsonb(row[c]) if c == 'qualite_preparee' else (json.dumps(row[c]) if c == 'contacts_whatsapp' and isinstance(row.get(c), (list,dict)) else row.get(c)) for c in COLUMNS) for row in rows])
            connection.execute('DELETE FROM public.annonces_preparation_audit')
            cursor.executemany('INSERT INTO public.annonces_preparation_audit (source_id,motif,lots) VALUES (%s,%s,%s)',
                               [(r['source_id'],r['motif'],r['lots']) for r in audit])
        connection.execute('CREATE INDEX IF NOT EXISTS annonces_preparees_zone_prix ON public.annonces_preparees (quartier_zone,prix_fcfa)')
        connection.execute('CREATE INDEX IF NOT EXISTS annonces_preparees_collecte ON public.annonces_preparees (premiere_collecte)')
        connection.execute('INSERT INTO public.annonces_preparation_runs (rapport) VALUES (%s)', (Jsonb(report),))
        return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--output', default='reports/annonces-preparees.json')
    args = parser.parse_args()
    settings = get_settings()
    if settings.database_url is None:
        raise SystemExit('DATABASE_URL absent.')
    try:
        with psycopg.connect(settings.database_url.get_secret_value(), row_factory=dict_row) as db:
            report = refresh(db, args.apply)
    except (psycopg.Error, ValueError) as exc:
        raise SystemExit('Préparation annulée, données précédentes conservées. Type : ' + type(exc).__name__) from None
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
