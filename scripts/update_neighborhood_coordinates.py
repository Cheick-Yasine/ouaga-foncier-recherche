#!/usr/bin/env python3
"""Complète le référentiel cartographique avec des lieux OSM strictement vérifiés.

Par défaut, le script est en simulation. Utiliser --apply pour enregistrer les
nouveaux repères dans app/data/neighborhoods_osm.json.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.neighborhoods import (
    ADMINISTRATIVE_AREAS,
    BROAD_AREAS,
    CITY_LEVEL_AREAS,
    KNOWN_NEIGHBORHOOD_ALIASES,
    PERIPHERAL_COMMUNES,
    PERIPHERAL_LOCALITIES,
    CANONICAL_NEIGHBORHOODS,
    neighborhood_key,
    neighborhood_metadata,
)

DATA_DIR = Path(__file__).resolve().parents[1] / "app" / "data"
OSM_FILE = DATA_DIR / "neighborhoods_osm.json"
GEONAMES_FILE = DATA_DIR / "neighborhoods_geonames.json"
CENTER = (12.3714, -1.5197)
# Rectangle de contrôle Grand Ouaga élargi. Il sert à rejeter les homonymes
# éloignés, pas à affirmer qu'un point appartient à la commune de Ouagadougou.
BOUNDS = {"south": 12.05, "north": 12.65, "west": -1.90, "east": -1.25}
ALLOWED_ADMIN = {
    neighborhood_key(value)
    for value in (
        "Ouagadougou", "Saaba", "Pabré", "Koubri", "Komsilga",
        "Loumbila", "Tanghin-Dassouri", "Komki-Ipala",
    )
}
ALLOWED_PLACE_TYPES = {
    "neighbourhood", "suburb", "quarter", "village", "hamlet",
    "locality", "isolated_dwelling",
}
EXCLUDED_ZONE_TYPES = (
    ADMINISTRATIVE_AREAS | BROAD_AREAS | CITY_LEVEL_AREAS
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def existing_keys() -> set[str]:
    keys: set[str] = set()
    for path in (GEONAMES_FILE, OSM_FILE):
        data = load_json(path)
        for item in data.get("locations", []):
            keys.add(neighborhood_key(item["name"]))
            keys.update(neighborhood_key(alias) for alias in item.get("aliases", []))
    return {key for key in keys if key}


def is_inside_bounds(result: dict) -> bool:
    try:
        south, north, west, east = map(float, result["boundingbox"])
        lat, lon = float(result["lat"]), float(result["lon"])
    except (KeyError, TypeError, ValueError):
        return False
    return (
        BOUNDS["south"] <= lat <= BOUNDS["north"]
        and BOUNDS["west"] <= lon <= BOUNDS["east"]
        and south <= lat <= north and west <= lon <= east
    )


def exact_osm_name(result: dict, canonical: str) -> bool:
    target = neighborhood_key(canonical)
    names = [result.get("name", "")]
    names.extend(
        value for key, value in result.get("namedetails", {}).items()
        if key in {"name", "name:fr", "official_name", "short_name"}
    )
    return any(neighborhood_key(str(value)) == target for value in names if value)


def is_grand_ouaga_result(result: dict) -> bool:
    address = result.get("address") or {}
    if neighborhood_key(address.get("country_code")) != "bf":
        return False
    values = {neighborhood_key(str(value)) for value in address.values()}
    return bool(values & ALLOWED_ADMIN)


def search_nominatim(name: str) -> list[dict]:
    params = urlencode({
        "q": f"{name}, Ouagadougou, Burkina Faso",
        "format": "jsonv2",
        "addressdetails": 1,
        "namedetails": 1,
        "extratags": 1,
        "limit": 5,
        "countrycodes": "bf",
        "viewbox": f'{BOUNDS["west"]},{BOUNDS["north"]},{BOUNDS["east"]},{BOUNDS["south"]}',
        "bounded": 1,
    })
    request = Request(
        "https://nominatim.openstreetmap.org/search?" + params,
        headers={
            "User-Agent": "HAKIMO-Ouaga-Foncier/1.0 (neighborhood reference maintenance)",
            "Accept": "application/json",
        },
    )
    with urlopen(request, timeout=20) as response:
        payload = json.load(response)
    if not isinstance(payload, list):
        return []
    return payload


def candidate_for(name: str) -> dict | None:
    try:
        results = search_nominatim(name)
    except Exception as exc:
        print(f"  ERREUR réseau : {exc}")
        return None

    matches = []
    for result in results:
        if result.get("class") != "place":
            continue
        if result.get("type") not in ALLOWED_PLACE_TYPES:
            continue
        if not exact_osm_name(result, name):
            continue
        if not is_inside_bounds(result) or not is_grand_ouaga_result(result):
            continue
        matches.append(result)

    # Plusieurs résultats exacts signifient que l'homonyme doit être vérifié
    # manuellement : ne pas choisir arbitrairement le premier.
    if len(matches) != 1:
        if len(matches) > 1:
            print(f"  AMBIGU : {len(matches)} résultats exacts dans le périmètre")
        return None

    result = matches[0]
    try:
        lat, lon = float(result["lat"]), float(result["lon"])
    except (KeyError, TypeError, ValueError):
        return None

    osm_type = str(result.get("osm_type", "")).lower()
    osm_id = result.get("osm_id")
    return {
        "name": name,
        "source_name": result.get("name", name),
        "aliases": [],
        "latitude": lat,
        "longitude": lon,
        "source_id": int(osm_id) if str(osm_id).isdigit() else None,
        "feature_type": osm_type,
        "point_kind": result.get("type"),
        "display_name": result.get("display_name", ""),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply", action="store_true",
        help="Enregistre les points validés dans neighborhoods_osm.json.",
    )
    args = parser.parse_args()

    osm_data = load_json(OSM_FILE)
    known = existing_keys()
    names = sorted(
        {
            neighborhood_metadata(name)["canonical"]
            for name in CANONICAL_NEIGHBORHOODS
            if neighborhood_metadata(name)["canonical"]
            and neighborhood_metadata(name)["zone_type"] in {
                "quartier", "localite_peripherique", "commune_peripherique"
            }
            and neighborhood_key(name) not in known
        },
        key=neighborhood_key,
    )

    print(f"Noms à rechercher : {len(names)}")
    print("Mode :", "ENREGISTREMENT" if args.apply else "SIMULATION")
    additions = []
    unresolved = []

    for index, name in enumerate(names, 1):
        print(f"[{index}/{len(names)}] {name}")
        point = candidate_for(name)
        if point:
            print(
                f'  OK : {point["latitude"]:.6f}, {point["longitude"]:.6f} '
                f'({point["point_kind"]}, OSM {point["source_id"]})'
            )
            additions.append(point)
        else:
            print("  À vérifier manuellement / aucun résultat assez fiable")
            unresolved.append(name)
        if index < len(names):
            time.sleep(1.1)

    print("\n===== BILAN =====")
    print("Nouveaux points validés :", len(additions))
    print("Noms non résolus :", len(unresolved))
    for name in unresolved:
        print(" -", name)

    if args.apply and additions:
        current = load_json(OSM_FILE)
        current["retrieved_at"] = date.today().isoformat()
        current["locations"].extend(additions)
        current["locations"].sort(key=lambda item: neighborhood_key(item["name"]))
        OSM_FILE.write_text(
            json.dumps(current, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"\nFichier mis à jour : {OSM_FILE}")
    elif not args.apply:
        print("\nSimulation uniquement : aucun fichier n'a été modifié.")
        print("Relancer avec --apply pour enregistrer les points validés.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
