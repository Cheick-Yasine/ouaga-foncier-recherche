"""Audite les prix après les phases précédentes sans modifier Neon."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from app.config import get_settings
from app.database import DatabaseNotConfiguredError
from app.price_control import build_price_control_audit


def audit_price_control() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    settings = get_settings()
    if settings.database_url is None:
        raise DatabaseNotConfiguredError(
            "DATABASE_URL n'est pas configurée dans l'environnement."
        )

    with psycopg.connect(
        settings.database_url.get_secret_value(),
        connect_timeout=10,
        row_factory=dict_row,
    ) as connection:
        with connection.transaction():
            connection.execute("SET TRANSACTION READ ONLY")
            rows = connection.execute(
                """
                SELECT
                    id::text AS id,
                    url,
                    texte_nettoye,
                    quartier_zone,
                    prix_fcfa,
                    superficie_m2,
                    premiere_collecte,
                    derniere_maj
                FROM public.annonces
                ORDER BY id
                """
            ).fetchall()

    return build_price_control_audit(rows)


def _write_trace(path: Path, trace: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = ["id", "statut_prix", "prix_etait_manquant", "decision"]
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(trace)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Contrôler les prix observés après préparation géographique."
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trace-output", type=Path, required=True)
    args = parser.parse_args()

    report, trace = audit_price_control()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    _write_trace(args.trace_output, trace)
    print(
        "Contrôle des prix simulé : "
        f"{report['observations_avant_controle_prix']} avant, "
        f"{report['observations_supprimees_controle_prix']} exclues, "
        f"{report['observations_restantes']} restantes."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
