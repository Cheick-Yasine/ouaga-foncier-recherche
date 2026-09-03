"""Teste la recherche complète sur Neon sans exposer de données sensibles."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

from app.search_engine import parse_search_description, rank_candidates
from app.search_repository import load_recent_candidates


def build_safe_report(
    description: str,
    max_age_days: int = 7,
    limit: int = 10,
) -> dict[str, object]:
    criteria = replace(
        parse_search_description(description),
        max_age_days=max_age_days,
    )
    candidates = load_recent_candidates(max_age_days)
    ranked = rank_candidates(criteria, candidates, limit=limit)

    return {
        "statut": "ok" if candidates and ranked else "a_verifier",
        "description_testee": description,
        "anciennete_maximale_jours": max_age_days,
        "candidats_charges": len(candidates),
        "resultats_classes": len(ranked),
        "criteres_interpretes": {
            "type_bien": criteria.property_type,
            "quartier": criteria.neighborhood,
            "prix_fcfa": criteria.price_fcfa,
            "prix_est_un_maximum": criteria.price_is_maximum,
            "superficie_m2": criteria.area_m2,
            "statut_document": criteria.document_status,
        },
        "scores": {
            "meilleur": ranked[0].score if ranked else None,
            "couverture_meilleure": ranked[0].coverage if ranked else None,
        },
        "donnees_non_exportees": [
            "DATABASE_URL",
            "identifiants_annonces",
            "liens_facebook",
            "texte_integral",
            "contacts_whatsapp",
            "prix_et_superficies_individuels",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Exécuter une recherche de contrôle sur Neon."
    )
    parser.add_argument(
        "--description",
        default="Je cherche une parcelle à Ouagadougou",
    )
    parser.add_argument("--max-age-days", type=int, default=7)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = build_safe_report(
        args.description,
        max_age_days=args.max_age_days,
        limit=args.limit,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "Recherche Neon terminée : "
        f"{report['candidats_charges']} candidats, "
        f"{report['resultats_classes']} résultats classés."
    )
    return 0 if report["statut"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
