"""Prépare ou applique la normalisation des types de biens sur Neon."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import psycopg

from app.config import get_settings
from app.database import DatabaseNotConfiguredError
from app.normalization import normalize_property_type


CONSTRAINT_NAME = "annonces_type_bien_normalise_check"
INDEX_NAME = "idx_annonces_type_bien_normalise"


def build_plan(connection: psycopg.Connection[Any]) -> tuple[list[tuple[str | None, str]], dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, type_bien, resume_court, texte_nettoye
            FROM public.annonces
            ORDER BY id
            """
        )
        rows = cursor.fetchall()

    updates: list[tuple[str | None, str]] = []
    original_counts: Counter[str] = Counter()
    normalized_counts: Counter[str] = Counter()

    for identifier, original_type, summary, clean_text in rows:
        original_counts[original_type or "<NULL>"] += 1
        normalized_type = normalize_property_type(
            original_type,
            summary,
            clean_text,
        )
        normalized_counts[normalized_type or "<A_CONFIRMER>"] += 1
        updates.append((normalized_type, identifier))

    report = {
        "total_rows": len(rows),
        "original_counts": dict(sorted(original_counts.items())),
        "normalized_counts": dict(sorted(normalized_counts.items())),
        "ambiguous_rows": normalized_counts["<A_CONFIRMER>"],
        "mapping": {
            "ferme": "terrain",
            "terrain": "terrain",
            "parcelle": "parcelle",
            "villa": "maison",
            "maison": "maison",
            "autre": "analyse prudente du texte, sinon valeur vide",
        },
    }
    return updates, report


def apply_plan(
    connection: psycopg.Connection[Any],
    updates: list[tuple[str | None, str]],
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            ALTER TABLE public.annonces
            ADD COLUMN IF NOT EXISTS type_bien_normalise TEXT
            """
        )
        cursor.executemany(
            """
            UPDATE public.annonces
            SET type_bien_normalise = %s
            WHERE id = %s
            """,
            updates,
        )
        cursor.execute(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = '{CONSTRAINT_NAME}'
                      AND conrelid = 'public.annonces'::regclass
                ) THEN
                    ALTER TABLE public.annonces
                    ADD CONSTRAINT {CONSTRAINT_NAME}
                    CHECK (
                        type_bien_normalise IS NULL
                        OR type_bien_normalise IN ('terrain', 'parcelle', 'maison')
                    ) NOT VALID;
                END IF;
            END
            $$;
            """
        )
        cursor.execute(
            f"""
            ALTER TABLE public.annonces
            VALIDATE CONSTRAINT {CONSTRAINT_NAME}
            """
        )
        cursor.execute(
            f"""
            CREATE INDEX IF NOT EXISTS {INDEX_NAME}
            ON public.annonces (type_bien_normalise)
            """
        )


def _json_default(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Normaliser les types de biens dans une colonne séparée."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Appliquer réellement la migration. Sans cette option : simulation.",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    settings = get_settings()
    if settings.database_url is None:
        raise DatabaseNotConfiguredError(
            "DATABASE_URL n'est pas configurée dans l'environnement."
        )

    with psycopg.connect(
        settings.database_url.get_secret_value(),
        connect_timeout=10,
    ) as connection:
        updates, report = build_plan(connection)
        report["mode"] = "apply" if args.apply else "dry-run"

        if args.apply:
            apply_plan(connection, updates)
            connection.commit()
            report["database_modified"] = True
        else:
            connection.rollback()
            report["database_modified"] = False

    rendered = json.dumps(
        report,
        ensure_ascii=False,
        indent=2,
        default=_json_default,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print(f"Rapport créé : {args.output}")
    else:
        print(rendered)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
