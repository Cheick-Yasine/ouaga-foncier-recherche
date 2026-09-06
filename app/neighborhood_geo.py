"""Repères cartographiques locaux : distances entre quartiers, jamais entre biens.

Le référentiel est embarqué : aucune géolocalisation de l'utilisateur et aucun
appel réseau pendant une recherche. Les sources et licences accompagnent les
données dans app/data et docs/cartographie.md.
"""
from __future__ import annotations

from functools import lru_cache
import json
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
from typing import Any

from app.neighborhoods import (
    ADMINISTRATIVE_AREAS, BROAD_AREAS, CITY_LEVEL_AREAS, neighborhood_key,
)

NEARBY_RADIUS_KM = 8.0
_DATA = Path(__file__).with_name("data")
_BROAD_KEYS = {neighborhood_key(n) for n in ADMINISTRATIVE_AREAS | BROAD_AREAS | CITY_LEVEL_AREAS}


@lru_cache(maxsize=1)
def _locations() -> dict[str, dict[str, Any] | None]:
    index: dict[str, dict[str, Any] | None] = {}
    for filename in ("neighborhoods_geonames.json", "neighborhoods_osm.json"):
        data = json.loads((_DATA / filename).read_text(encoding="utf-8"))
        for entry in data["locations"]:
            point = dict(entry, source=data["source"], attribution=data["attribution"],
                         license_url=data["license_url"], retrieved_at=data["retrieved_at"])
            for name in {entry["name"], *entry["aliases"]}:
                key = neighborhood_key(name)
                # A collision is unresolved, never silently assigned to one place.
                if key in index and index[key] != point:
                    index[key] = None
                else:
                    index[key] = point
    return index


def location_for(name: str | None) -> dict[str, Any] | None:
    key = neighborhood_key(name)
    if not key or key in _BROAD_KEYS:
        return None
    point = _locations().get(key)
    return dict(point) if point else None


def distance_km(origin: str | None, destination: str | None) -> float | None:
    """Distance géodésique non arrondie entre les repères WGS84 des zones."""
    a, b = location_for(origin), location_for(destination)
    if not a or not b:
        return None
    lat_a, lat_b = radians(a["latitude"]), radians(b["latitude"])
    d_lat = lat_b - lat_a
    d_lon = radians(b["longitude"] - a["longitude"])
    haversine = sin(d_lat / 2) ** 2 + cos(lat_a) * cos(lat_b) * sin(d_lon / 2) ** 2
    return 6371.0088 * 2 * asin(sqrt(min(1.0, max(0.0, haversine))))


def neighborhood_relation(origin: str | None, destination: str | None) -> dict[str, Any] | None:
    """Décrit le même quartier ou un voisin vérifié dans le rayon configuré.

    Deux annonces dans le même quartier ne sont pas distantes de zéro km : leur
    emplacement exact est inconnu. Pour un quartier inconnu, seules les mentions
    littérales identiques sont acceptées, sans distance inventée.
    """
    a_key, b_key = neighborhood_key(origin), neighborhood_key(destination)
    if not a_key or not b_key or a_key in _BROAD_KEYS or b_key in _BROAD_KEYS:
        return None
    a, b = location_for(origin), location_for(destination)
    same = a_key == b_key or bool(a and b and a["name"] == b["name"])
    if same:
        return {"quartier_origine": origin, "meme_quartier": True, "distance_km": None,
                "distance_libelle": "Même quartier"}
    distance = distance_km(origin, destination)
    if distance is None or distance > NEARBY_RADIUS_KM:
        return None
    rounded = round(distance, 1)
    label = f"≈ {rounded:g} km de {origin}".replace(".", ",") if rounded else f"Moins de 0,1 km de {origin}"
    return {
        "quartier_origine": origin, "meme_quartier": False,
        "distance_km": rounded, "distance_libelle": label,
        "distance_type": "ligne_droite_entre_reperes_de_quartiers",
        "sources": sorted({a["source"], b["source"]}),
        "carte_url": f"https://www.openstreetmap.org/?mlat={b['latitude']}&mlon={b['longitude']}#map=14/{b['latitude']}/{b['longitude']}",
    }
