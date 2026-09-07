"""Contraintes explicites de l'utilisateur, conservées malgré la reformulation LLM."""
from __future__ import annotations

from collections.abc import Sequence
import math
import re
from typing import Any

from app.search_engine import parse_search_description
from app.text_features import normalize_text
from app.listing_scope import city_only_request, within_ouagadougou, sale_eligible
from app.neighborhoods import detect_neighborhoods, detect_out_of_scope_locality


def conversation_city_only(message: str, history: Sequence[Any]) -> bool:
    for source in [message, *(item.content for item in reversed(history) if item.role == 'user')]:
        own_text = re.split(r"(?i)(?:voici\s+l[’'](?:annonce|publication)|(?:annonce|publication)\s*(?:à analyser)?)\s*:", source, maxsplit=1)[0]
        if detect_neighborhoods(own_text) or detect_out_of_scope_locality(own_text):
            return city_only_request(own_text)
        if re.search(r'\b(?:elargis|elargir|inclus|ajoute)\b.{0,25}\b(?:environs|peripherie)\b', normalize_text(own_text)):
            return False
    return False


def respect_search_scope(payload: dict[str, Any], city_only: bool, description: str) -> dict[str, Any]:
    rows = payload.get('results')
    kept = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or not sale_eligible(str(row.get('description') or '')):
            continue
        in_city = row.get('dans_ouagadougou')
        if city_only and not (in_city is True or (in_city is None and within_ouagadougou(str(row.get('description') or ''), row.get('quartier')))):
            continue
        kept.append(row)
    criteria = dict(payload.get('criteres') or {})
    if city_only:
        criteria.update(ouagadougou_uniquement=True, description=description)
    return {**payload, 'criteres': criteria, 'results': kept, 'nombre_resultats': len(kept)}


def conversation_budget(message: str, history: Sequence[Any]) -> float | None:
    """Prend le dernier plafond explicite dans les messages de l'utilisateur.

    Les réponses du modèle et les montants d'une publication introduite par
    « Voici l'annonce : » ne définissent pas le budget de l'acheteur.
    """
    sources = [message, *(item.content for item in reversed(history) if item.role == 'user')]
    for source in sources:
        own_text = re.split(r"(?i)(?:voici\s+l[’'](?:annonce|publication)|(?:annonce|publication)\s*(?:à analyser)?)\s*:", source, maxsplit=1)[0]
        if re.search(r"\b(?:sans (?:limite de budget|plafond|budget maximum)|(?:retire|enleve|supprime|oublie).{0,20}(?:limite|plafond|budget))\b", normalize_text(own_text)):
            return None
        criteria = parse_search_description(own_text)
        if criteria.price_is_maximum and criteria.price_fcfa is not None:
            return criteria.price_fcfa
    return None


def budget_description(description: str, budget: float) -> str:
    # Corriger un budget reformulé, sans laisser deux plafonds contradictoires
    # dans la recherche enregistrée. Les autres critères restent intacts.
    amount = f"{budget:.2f}".rstrip('0').rstrip('.')
    canonical = f"Budget maximum {amount} FCFA"
    pattern = r"\bbudget(?:\s+(?:maximum|maximal|max|est|passe|de|à|a))*\s*[:=]?\s*\d(?:[\d\s.,]*\d)?(?:\s*(?:millions?|milliards?)(?:\s+\d{3}\b)?)?(?:\s*(?:fcfa|f\s+cfa|cfa))?"
    rewritten = re.sub(pattern, canonical, description, flags=re.IGNORECASE)
    parsed = parse_search_description(rewritten)
    return rewritten if parsed.price_is_maximum and parsed.price_fcfa == budget else f"{canonical}. {rewritten}"


def respect_search_budget(payload: dict[str, Any], budget: float, description: str) -> dict[str, Any]:
    """Même liste plafonnée pour le conseil du modèle, la carte et le tableau."""
    def within_budget(item: Any) -> bool:
        if not isinstance(item, dict) or isinstance(item.get('prix_fcfa'), bool):
            return False
        try:
            price = float(item['prix_fcfa'])
        except (KeyError, ValueError, TypeError):
            return False
        return math.isfinite(price) and 0 < price <= budget

    rows = payload.get('results')
    rows = [item for item in rows if within_budget(item)] if isinstance(rows, list) else []
    criteria = dict(payload.get('criteres') or {})
    criteria.update(description=description, prix_fcfa=budget, prix_est_un_maximum=True)
    return {**payload, 'criteres': criteria, 'results': rows, 'nombre_resultats': len(rows)}
