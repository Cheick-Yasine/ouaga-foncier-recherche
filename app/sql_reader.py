"""Execute model-written SELECT queries on annonces, never model-written mutations."""
from __future__ import annotations

import re
from typing import Any

import psycopg
from psycopg.rows import dict_row
import sqlglot
from sqlglot import exp

from app.config import get_settings
from app.public_references import public_announcement_id


class SQLReadError(ValueError):
    pass


COLUMNS = frozenset({
    'id', 'date_publication', 'premiere_collecte', 'type_bien',
    'type_bien_normalise', 'quartier_zone', 'superficie_m2', 'prix_fcfa',
    'statut_document', 'resume_court', 'texte_nettoye',
})
# Closed grammar: no user functions, joins, subqueries, catalogs or locking clauses.
NODES = frozenset({
    'Select', 'From', 'Table', 'Identifier', 'Column', 'Where', 'Order',
    'Ordered', 'Limit', 'Literal', 'Null', 'Boolean', 'Paren',
    'And', 'Or', 'Not', 'EQ', 'NEQ', 'GT', 'GTE', 'LT', 'LTE',
    'Is', 'In', 'Between', 'Like', 'ILike', 'Add', 'Sub', 'Mul', 'Div',
    'Neg', 'Lower', 'Upper', 'Coalesce', 'Nullif', 'Abs', 'Round',
})


def validate_select(sql: str) -> str:
    if not isinstance(sql, str) or not sql.strip() or len(sql) > 8000:
        raise SQLReadError('Requête vide ou trop longue.')
    try:
        statements = sqlglot.parse(sql, read='postgres')
    except sqlglot.errors.ParseError:
        raise SQLReadError('SQL invalide. Utilise un SELECT PostgreSQL simple.') from None
    if len(statements) != 1 or not isinstance(statements[0], exp.Select):
        raise SQLReadError('Une seule requête SELECT est autorisée.')
    query = statements[0]
    for node in query.walk():
        if type(node).__name__ not in NODES:
            raise SQLReadError('Construction SQL non autorisée : ' + type(node).__name__)
    tables = list(query.find_all(exp.Table))
    if len(tables) != 1 or tables[0].name != 'annonces' or tables[0].db not in ('', 'public') or tables[0].catalog:
        raise SQLReadError('Seule la table public.annonces est accessible.')
    if tables[0].alias:
        raise SQLReadError('Utilise la table sans alias.')
    for column in query.find_all(exp.Column):
        if column.name not in COLUMNS or column.table not in ('', 'annonces') or column.db or column.catalog:
            raise SQLReadError('Colonne non autorisée. Consulte le schéma fourni.')
    projection = query.expressions
    if len(projection) != 1 or not isinstance(projection[0], exp.Column) or projection[0].name != 'id':
        raise SQLReadError('Écris SELECT id FROM public.annonces ; les détails seront joints automatiquement.')
    tables[0].set('db', exp.to_identifier('public'))
    limit = query.args.get('limit')
    if limit is not None:
        value = limit.expression
        if not isinstance(value, exp.Literal) or value.is_string or not value.this.isdigit():
            raise SQLReadError('LIMIT doit être un entier entre 1 et 100.')
        if not 1 <= int(value.this) <= 100:
            raise SQLReadError('LIMIT doit être compris entre 1 et 100.')
    else:
        query = query.limit(100)
    return query.sql(dialect='postgres')


def query_annonces(sql: str, *, settings=None) -> list[dict[str, Any]]:
    """No ranking or business filtering: preserve the database result order."""
    validated = validate_select(sql)
    current = settings or get_settings()
    url = current.assistant_database_url or current.database_url
    if url is None:
        raise SQLReadError('La connexion à la base des annonces est absente.')
    try:
        with psycopg.connect(url.get_secret_value(), row_factory=dict_row) as connection:
            with connection.transaction():
                connection.execute('SET TRANSACTION READ ONLY')
                connection.execute("SET LOCAL search_path = pg_catalog")
                connection.execute("SET LOCAL statement_timeout = '20s'")
                connection.execute("SET LOCAL lock_timeout = '2s'")
                selected = connection.execute(validated).fetchall()
                ids = [str(row['id']) for row in selected]
                if not ids:
                    return []
                rows = connection.execute('''
                    SELECT id::text AS id, url, date_publication, premiere_collecte,
                           type_bien, type_bien_normalise, quartier_zone,
                           superficie_m2, prix_fcfa, statut_document,
                           resume_court, texte_nettoye
                    FROM public.annonces WHERE id::text = ANY(%s)
                ''', (ids,)).fetchall()
        by_id = {row['id']: row for row in rows}
        return [by_id[identifier] for identifier in ids if identifier in by_id]
    except psycopg.Error:
        # Database diagnostics can contain SQL, values and deployment details.
        raise SQLReadError('La requête a échoué ou dépassé sa durée autorisée. Simplifie-la et vérifie les colonnes.') from None


def read_references(references: list[str], *, settings=None, include_contacts=False) -> list[dict[str, Any]]:
    """Resolve existing opaque references without exposing raw database IDs."""
    if not isinstance(references, list) or not 1 <= len(references) <= (500 if include_contacts else 10) or any(
        not isinstance(ref, str) or not re.fullmatch(r'[0-9a-f]{24}', ref) for ref in references
    ):
        raise SQLReadError('Fournis entre 1 et 10 références publiques reçues précédemment.')
    current = settings or get_settings()
    url = current.database_url if include_contacts else (current.assistant_database_url or current.database_url)
    if url is None:
        raise SQLReadError('La connexion à la base des annonces est absente.')
    try:
        with psycopg.connect(url.get_secret_value(), row_factory=dict_row) as connection:
            with connection.transaction():
                connection.execute('SET TRANSACTION READ ONLY')
                connection.execute("SET LOCAL statement_timeout = '20s'")
                wanted = set(references)
                found = {}
                # Only IDs are scanned, never publication texts or contacts.
                with connection.cursor(name='hakimo_references') as cursor:
                    cursor.execute('SELECT id::text AS id FROM public.annonces')
                    for row in cursor:
                        ref = public_announcement_id(row['id'])
                        if ref in wanted:
                            found[ref] = row['id']
                        if len(found) == len(wanted):
                            break
                ids = [found[ref] for ref in references if ref in found]
                if not ids:
                    return []
                contact_column = ', contacts_whatsapp' if include_contacts else ''
                rows = connection.execute(f'''SELECT id::text AS id, url, date_publication,
                    premiere_collecte, type_bien, type_bien_normalise, quartier_zone,
                    superficie_m2, prix_fcfa, statut_document, resume_court, texte_nettoye {contact_column}
                    FROM public.annonces WHERE id::text = ANY(%s)''', (ids,)).fetchall()
                by_id = {row['id']: row for row in rows}
                return [by_id[identifier] for identifier in ids if identifier in by_id]
    except psycopg.Error:
        raise SQLReadError('La relecture des annonces est temporairement indisponible.') from None
