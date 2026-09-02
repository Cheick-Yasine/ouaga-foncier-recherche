"""Inventorie les quartiers présents dans Neon sans modifier la base."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import psycopg

from app.config import get_settings
from app.database import DatabaseNotConfiguredError
from app.neighborhoods import (
    group_variants,
    neighborhood_key,
    suggest_canonical_neighborhood,
)


def _clean_report_value(value: str) -> str:
    """Empêche les retours à la ligne et limite les champs manifestement sales."""

    return " ".join(value.split())[:200]


def build_neighborhood_report(
    rows: list[tuple[str | None, int]],
) -> dict[str, Any]:
    missing_rows = sum(count for value, count in rows if value is None)
    non_null_values = [
        (_clean_report_value(value), int(count))
        for value, count in rows
        if value is not None and value.strip()
    ]
    groups = group_variants(non_null_values)

    suggestion_counts: Counter[str] = Counter()
    all_values: list[dict[str, Any]] = []
    for raw_value, count in sorted(
        non_null_values,
        key=lambda item: (-item[1], item[0].casefold()),
    ):
        suggestion = suggest_canonical_neighborhood(raw_value)
        if suggestion:
            suggestion_counts[suggestion] += count
        all_values.append(
            {
                "original": raw_value,
                "occurrences": count,
                "comparison_key": neighborhood_key(raw_value),
                "suggested_canonical": suggestion,
                "status": "known_alias" if suggestion else "review_required",
            }
        )

    variant_clusters = []
    for key, variants in groups.items():
        distinct_spellings = {raw for raw, _ in variants}
        if len(distinct_spellings) < 2:
            continue
        variant_clusters.append(
            {
                "comparison_key": key,
                "total_occurrences": sum(count for _, count in variants),
                "suggested_canonical": suggest_canonical_neighborhood(
                    variants[0][0]
                ),
                "variants": [
                    {"value": raw, "occurrences": count}
                    for raw, count in sorted(
                        variants,
                        key=lambda item: (-item[1], item[0].casefold()),
                    )
                ],
            }
        )
    variant_clusters.sort(
        key=lambda cluster: (
            -cluster["total_occurrences"],
            cluster["comparison_key"],
        )
    )

    return {
        "table": "public.annonces",
        "source_column": "quartier_zone",
        "total_rows": sum(int(count) for _, count in rows),
        "missing_rows": missing_rows,
        "distinct_non_null_values": len(non_null_values),
        "known_alias_rows": sum(suggestion_counts.values()),
        "known_alias_counts": dict(sorted(suggestion_counts.items())),
        "variant_cluster_count": len(variant_clusters),
        "variant_clusters": variant_clusters,
        "all_values": all_values,
        "read_only": True,
        "database_modified": False,
    }


def audit_neighborhoods() -> dict[str, Any]:
    settings = get_settings()
    if settings.database_url is None:
        raise DatabaseNotConfiguredError(
            "DATABASE_URL n'est pas configurée dans l'environnement."
        )

    with psycopg.connect(
        settings.database_url.get_secret_value(),
        connect_timeout=10,
    ) as connection:
        with connection.transaction():
            connection.execute("SET TRANSACTION READ ONLY")
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT quartier_zone, COUNT(*)
                    FROM public.annonces
                    GROUP BY quartier_zone
                    ORDER BY COUNT(*) DESC, quartier_zone
                    """
                )
                rows = cursor.fetchall()

    return build_neighborhood_report(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inventorier les variantes de quartiers dans Neon."
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = audit_neighborhoods()
    rendered = json.dumps(report, ensure_ascii=False, indent=2)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print(f"Rapport créé : {args.output}")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
