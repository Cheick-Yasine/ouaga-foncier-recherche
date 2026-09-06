"""Exclusions communes à la recherche, au MCP et aux chiffres de l'accueil."""
from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from app.neighborhoods import (
    ADMINISTRATIVE_AREAS, BROAD_AREAS, CITY_LEVEL_AREAS,
    detect_out_of_scope_locality, local_neighborhood, neighborhood_key,
    resolve_neighborhood,
)


def sale_eligible(text: str) -> bool:
    """Écarte les locations, annonces mixtes, demandes et biens retirés.

    Une mention « vente » ne neutralise jamais une offre de location. Les fiches
    peu détaillées restent possibles, sans leur attribuer une disponibilité.
    """
    normalized = neighborhood_key(text)
    # « Pas de location » exprime au contraire une vente seule.
    normalized = re.sub(r"\b(?:pas de|sans|non disponible (?:a|en)) location\b", "", normalized)
    excluded = (
        r"\b(?:a louer|en location|mise? en location|location|loyer|caution|bail|loue[er]?)\b",
        r"\b(?:par|le|au) mois\b|\bmensuel(?:le)?\b|\b(?:fcfa|cfa) mois\b",
        r"\b(?:deja vendu[es]*|vendu[es]*|plus disponible|pas (?:a vendre|en vente)|retire[es]* de la vente)\b",
        r"\b(?:je|nous) (?:cherche|cherchons|recherche|recherchons)\b",
        r"\b(?:cherche|recherche|recherchons) (?:un|une|des) (?:terrain|parcelle|maison)\b",
    )
    return not any(re.search(pattern, normalized) for pattern in excluded)


def city_only_request(description: str) -> bool:
    text = re.sub(r"\b(?:ouaga|ouagadougou) 2000\b", "", neighborhood_key(description))
    if not re.search(r"\b(?:ouaga|ouagadougou)\b", text):
        return False
    if re.search(r"\b(?:uniquement|seulement|strictement|exclusivement)(?: a| dans(?: la ville de)?| la ville de)? (?:ouaga|ouagadougou)\b|\b(?:ouaga|ouagadougou) (?:seulement|uniquement)\b|\bsans (?:les )?(?:environs|peripherie)\b", text):
        return True
    return not re.search(r"\b(?:environs|peripherie|alentours|autour)\b", text)


@lru_cache(maxsize=1)
def _city_places() -> dict[str, bool]:
    data = json.loads(Path(__file__).with_name('data').joinpath('ouagadougou_scope.json').read_text(encoding='utf-8'))
    places: dict[str, bool] = {}
    for entry in data['locations']:
        for name in [entry['name'], *entry['aliases']]:
            key = neighborhood_key(name)
            places[key] = bool(entry['in_city']) and places.get(key, True)
    return places


def within_ouagadougou(text: str, neighborhood: str | None) -> bool:
    """Une zone inconnue ou extérieure ne satisfait pas « Ouagadougou seule »."""
    if detect_out_of_scope_locality(text) or detect_out_of_scope_locality(neighborhood):
        return False
    commune = re.search(r"\bcommune(?: rurale)? (?:de|du) ([a-z]+)", neighborhood_key(text))
    if commune and commune[1] not in {'ouagadougou', 'ouaga'}:
        return False
    name = local_neighborhood(text, neighborhood)
    if name:
        return _city_places().get(neighborhood_key(name), False)
    resolution = resolve_neighborhood(text, neighborhood)
    if resolution.canonical in CITY_LEVEL_AREAS | ADMINISTRATIVE_AREAS | BROAD_AREAS:
        return True
    return _city_places().get(neighborhood_key(resolution.canonical), False)


def facebook_publication_url(raw: str | None) -> str | None:
    """Lien source Facebook uniquement, jamais une redirection de l'application."""
    if not raw or any(ord(c) < 32 for c in raw):
        return None
    try:
        parsed = urlsplit(raw.strip())
        host = (parsed.hostname or '').lower()
        valid_host = any(host == d or host.endswith('.' + d) for d in ('facebook.com', 'fb.com', 'fb.watch'))
        if parsed.scheme not in {'https', 'http'} or not valid_host or parsed.username or parsed.password:
            return None
        if parsed.path.rstrip('/') in {'', '/l.php', '/login', '/login.php', '/sharer.php', '/dialog/share'}:
            return None
        return raw.strip()
    except ValueError:
        return None
