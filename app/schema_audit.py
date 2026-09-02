"""Audit en lecture seule de la table public.annonces sur Neon."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import psycopg
from psycopg import sql

from app.config import Settings, get_settings
from app.database import DatabaseNotConfiguredError


EXPECTED_ANNONCE_COLUMNS = {
    "id": "text",
    "groupe_nom": "text",
    "url": "text",
    "date_publication": "text",
    "date_incertaine": "boolean",
    "type_bien": "text",
    "quartier_zone": "text",
    "superficie_m2": "integer",
    "prix_fcfa": "integer",
    "statut_document": "text",
    "contacts_whatsapp": "text",
    "mots_cles_pertinents": "text",
    "resume_court": "text",
    "texte_nettoye": "text",
    "premiere_collecte": "timestamp with time zone",
    "derniere_maj": "timestamp with time zone",
}


@dataclass(frozen=True)
class ColumnInfo:
    name: str
    data_type: str
    nullable: bool
    position: int


def compare_expected_schema(columns: list[ColumnInfo]) -> dict[str, Any]:
    """Compare le schéma observé au contrat produit par l'ETL."""

    observed = {column.name: column.data_type for column in columns}
    missing = sorted(set(EXPECTED_ANNONCE_COLUMNS) - set(observed))
    unexpected = sorted(set(observed) - set(EXPECTED_ANNONCE_COLUMNS))
    type_mismatches = [
        {
            "column": name,
            "expected": expected_type,
            "observed": observed[name],
        }
        for name, expected_type in EXPECTED_ANNONCE_COLUMNS.items()
        if name in observed and observed[name] != expected_type
    ]

    recommendations: list[str] = []
    if observed.get("date_publication") == "text":
        recommendations.append(
            "Convertir ou compléter date_publication par une colonne TIMESTAMPTZ "
            "avant d'appliquer le filtre strict des 7 derniers jours."
        )
    if "contacts_whatsapp" in observed:
        recommendations.append(
            "Traiter contacts_whatsapp comme donnée personnelle et ne jamais "
            "l'exposer sans contrôle dans une API publique."
        )

    return {
        "missing_columns": missing,
        "unexpected_columns": unexpected,
        "type_mismatches": type_mismatches,
        "recommendations": recommendations,
    }


def _fetch_columns(cursor: psycopg.Cursor[Any]) -> list[ColumnInfo]:
    cursor.execute(
        """
        SELECT column_name, data_type, is_nullable, ordinal_position
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'annonces'
        ORDER BY ordinal_position
        """
    )
    return [
        ColumnInfo(
            name=row[0],
            data_type=row[1],
            nullable=row[2] == "YES",
            position=row[3],
        )
        for row in cursor.fetchall()
    ]


def _fetch_null_counts(
    cursor: psycopg.Cursor[Any],
    columns: list[ColumnInfo],
) -> tuple[int, dict[str, int]]:
    expressions = [
        sql.SQL("COUNT(*) FILTER (WHERE {} IS NULL)").format(
            sql.Identifier(column.name)
        )
        for column in columns
    ]
    query = sql.SQL("SELECT COUNT(*), {} FROM public.annonces").format(
        sql.SQL(", ").join(expressions)
    )
    cursor.execute(query)
    row = cursor.fetchone()
    if row is None:
        return 0, {}
    return int(row[0]), {
        column.name: int(row[index + 1])
        for index, column in enumerate(columns)
    }


def _fetch_top_values(
    cursor: psycopg.Cursor[Any],
    column_name: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    query = sql.SQL(
        """
        SELECT {column}::text AS value, COUNT(*) AS occurrences
        FROM public.annonces
        GROUP BY {column}
        ORDER BY occurrences DESC, value
        LIMIT %s
        """
    ).format(column=sql.Identifier(column_name))
    cursor.execute(query, (limit,))
    return [
        {"value": value, "occurrences": int(count)}
        for value, count in cursor.fetchall()
    ]


def audit_annonces_schema(settings: Settings | None = None) -> dict[str, Any]:
    """Produit un rapport statistique sans écrire ni modifier la base."""

    current_settings = settings or get_settings()
    if current_settings.database_url is None:
        raise DatabaseNotConfiguredError(
            "DATABASE_URL n'est pas configurée dans l'environnement."
        )

    database_url = current_settings.database_url.get_secret_value()
    with psycopg.connect(database_url, connect_timeout=10) as connection:
        with connection.transaction():
            connection.execute("SET TRANSACTION READ ONLY")
            with connection.cursor() as cursor:
                columns = _fetch_columns(cursor)
                if not columns:
                    return {
                        "table": "public.annonces",
                        "table_exists": False,
                        "columns": [],
                        "comparison": compare_expected_schema([]),
                    }

                total_rows, null_counts = _fetch_null_counts(cursor, columns)

                cursor.execute(
                    """
                    SELECT constraint_type, column_name
                    FROM information_schema.table_constraints AS tc
                    LEFT JOIN information_schema.key_column_usage AS kcu
                      ON tc.constraint_name = kcu.constraint_name
                     AND tc.table_schema = kcu.table_schema
                    WHERE tc.table_schema = 'public'
                      AND tc.table_name = 'annonces'
                    ORDER BY constraint_type, ordinal_position
                    """
                )
                constraints = [
                    {"type": row[0], "column": row[1]}
                    for row in cursor.fetchall()
                ]

                cursor.execute(
                    """
                    SELECT indexname, indexdef
                    FROM pg_indexes
                    WHERE schemaname = 'public' AND tablename = 'annonces'
                    ORDER BY indexname
                    """
                )
                indexes = [
                    {"name": row[0], "definition": row[1]}
                    for row in cursor.fetchall()
                ]

                column_names = {column.name for column in columns}
                date_range: dict[str, Any] = {}
                if {"premiere_collecte", "derniere_maj"} <= column_names:
                    cursor.execute(
                        """
                        SELECT MIN(premiere_collecte), MAX(derniere_maj)
                        FROM public.annonces
                        """
                    )
                    row = cursor.fetchone()
                    if row:
                        date_range = {
                            "first_collection": row[0],
                            "last_update": row[1],
                        }

                distributions = {
                    name: _fetch_top_values(cursor, name)
                    for name in (
                        "type_bien",
                        "quartier_zone",
                        "statut_document",
                    )
                    if name in column_names
                }

    return {
        "table": "public.annonces",
        "table_exists": True,
        "total_rows": total_rows,
        "columns": [asdict(column) for column in columns],
        "null_counts": null_counts,
        "constraints": constraints,
        "indexes": indexes,
        "date_range": date_range,
        "top_values": distributions,
        "comparison": compare_expected_schema(columns),
        "read_only": True,
    }
