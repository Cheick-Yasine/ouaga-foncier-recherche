#!/usr/bin/env python3
"""Audit quartier par quartier des coordonnées cartographiques.

Le script ne modifie aucune coordonnée. Il compare le référentiel embarqué
(GeoNames/OSM) avec une recherche Nominatim/OSM et produit un CSV d'audit.
Les cas ambigus ou trop éloignés doivent être validés manuellement avant
toute modification du référentiel.
"""

from __future__ import annotations

import csv
import json
import math
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.neighborhoods import KNOWN_NEIGHBORHOOD_ALIASES, neighborhood_key
from app.neighborhood_geo import location_for

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "neighborhood_coordinates_audit.csv"
USER_AGENT = "Hakimo-Ouaga-Foncier-coordinate-audit/1.0"
MIN_DELAY = 1.1
last_request = 0.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return r * 2 * math.asin(math.sqrt(min(1.0, max(0.0, h))))


def nominatim(name: str) -> dict | None:
    global last_request
    wait = MIN_DELAY - (time.monotonic() - last_request)
    if wait > 0:
        time.sleep(wait)

    params = urlencode({
        "q": f"{name}, Ouagadougou, Burkina Faso",
        "format": "jsonv2",
        "limit": 5,
        "countrycodes": "bf",
        "addressdetails": 1,
    })
    req = Request(
        f"https://nominatim.openstreetmap.org/search?{params}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urlopen(req, timeout=15) as response:
            data = json.load(response)
    except Exception as exc:
        return {"error": str(exc)}
    finally:
        last_request = time.monotonic()

    if not isinstance(data, list) or not data:
        return None

    # On conserve les 5 résultats afin de pouvoir repérer les homonymes.
    candidates = []
    for item in data:
        try:
            candidates.append({
                "lat": float(item["lat"]),
                "lon": float(item["lon"]),
                "display_name": item.get("display_name", ""),
                "type": item.get("type", ""),
                "class": item.get("class", ""),
                "osm_id": item.get("osm_id", ""),
            })
        except (KeyError, TypeError, ValueError):
            continue
    return {"candidates": candidates}


def classify(existing: dict | None, online: dict | None) -> tuple[str, float | None]:
    if existing is None and online is None:
        return "ABSENT", None
    if existing is None:
        return "A_VALIDER_NOUVELLE_COORDONNEE", None
    if online is None or "candidates" not in online or not online["candidates"]:
        return "AUCUNE_CORRESPONDANCE_EN_LIGNE", None

    distances = [
        haversine_km(
            float(existing["latitude"]),
            float(existing["longitude"]),
            c["lat"],
            c["lon"],
        )
        for c in online["candidates"]
    ]
    best = min(distances)

    if best <= 0.15:
        return "OK", best
    if best <= 0.75:
        return "ECART_A_VERIFIER", best
    return "ECART IMPORTANT", best


def main() -> None:
    names = sorted(
        set(KNOWN_NEIGHBORHOOD_ALIASES.values()),
        key=neighborhood_key,
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for i, name in enumerate(names, 1):
        existing = location_for(name)
        online = nominatim(name)
        status, distance = classify(existing, online)
        candidates = (online or {}).get("candidates", []) if isinstance(online, dict) else []

        rows.append({
            "quartier": name,
            "statut": status,
            "source_actuelle": existing.get("source", "") if existing else "",
            "latitude_actuelle": existing.get("latitude", "") if existing else "",
            "longitude_actuelle": existing.get("longitude", "") if existing else "",
            "meilleure_distance_km": round(distance, 3) if distance is not None else "",
            "candidat_osm_1": candidates[0].get("display_name", "") if candidates else "",
            "latitude_osm_1": candidates[0].get("lat", "") if candidates else "",
            "longitude_osm_1": candidates[0].get("lon", "") if candidates else "",
            "nb_candidats_osm": len(candidates),
        })
        print(f"[{i}/{len(names)}] {name}: {status}")

    fields = list(rows[0])
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    counts = {}
    for row in rows:
        counts[row["statut"]] = counts.get(row["statut"], 0) + 1

    print("\n=== RÉSUMÉ ===")
    for status, count in sorted(counts.items()):
        print(f"{status}: {count}")
    print(f"\nRapport: {OUT}")


if __name__ == "__main__":
    main()
