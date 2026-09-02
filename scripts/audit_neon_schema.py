"""Génère un rapport JSON sur public.annonces sans modifier Neon."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.schema_audit import audit_annonces_schema


def _json_default(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Auditer en lecture seule la table public.annonces sur Neon."
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Chemin facultatif du rapport JSON.",
    )
    args = parser.parse_args()

    report = audit_annonces_schema()
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

    return 0 if report.get("table_exists") else 2


if __name__ == "__main__":
    raise SystemExit(main())
