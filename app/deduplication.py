"""Déduplication déterministe et traçable des annonces."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from app.neighborhoods import neighborhood_key


REFERENCE_COUNTS = {
    "observations_avant": 11_245,
    "observations_supprimees": 6_694,
    "observations_restantes": 4_551,
}

_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")
_MIN_TEXT_KEY_LENGTH = 20


def normalized_text_key(value: str | None) -> str:
    """Normalise un texte sans conserver son contenu dans les rapports."""

    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", str(value))
    without_accents = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    simplified = _NON_ALPHANUMERIC.sub(" ", without_accents.casefold())
    return " ".join(simplified.split())


def normalized_url_key(value: str | None) -> str:
    """Retire les paramètres de suivi d'une URL avant comparaison."""

    if not value:
        return ""
    raw = str(value).strip()
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
    except ValueError:
        return raw.casefold().rstrip("/")
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.casefold(), parts.netloc.casefold(), path, "", ""))


def _positive_integer(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except Exception:
        return None
    if not number.is_finite() or number <= 0 or number != number.to_integral_value():
        return None
    return int(number)


def characteristic_key(row: Mapping[str, Any]) -> tuple[str, int, int] | None:
    """Construit une clé candidate, jamais suffisante pour supprimer seule."""

    area = neighborhood_key(row.get("quartier_zone"))
    price = _positive_integer(row.get("prix_fcfa"))
    surface = _positive_integer(row.get("superficie_m2"))
    if not area or price is None or surface is None:
        return None
    return area, price, surface


def _datetime_key(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    return datetime.min.replace(tzinfo=timezone.utc)


def _completeness(row: Mapping[str, Any]) -> int:
    return sum(
        row.get(column) not in (None, "")
        for column in (
            "url",
            "texte_nettoye",
            "quartier_zone",
            "prix_fcfa",
            "superficie_m2",
        )
    )


def _keeper_sort_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    """Privilégie la republication la plus récente, puis la plus complète."""

    return (
        _datetime_key(row.get("derniere_maj")),
        _datetime_key(row.get("premiere_collecte")),
        _completeness(row),
        str(row.get("id") or ""),
    )


def _hash_key(namespace: str, value: Any) -> str:
    payload = f"{namespace}:{value!r}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


class _DisjointSet:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, first: int, second: int) -> None:
        root_first, root_second = self.find(first), self.find(second)
        if root_first != root_second:
            self.parent[root_second] = root_first


def build_deduplication_audit(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Identifie les doublons certains et les candidats sans modifier la source."""

    row_list = list(rows)
    identifiers = [str(row.get("id") or "") for row in row_list]
    if any(not identifier for identifier in identifiers):
        raise ValueError("Chaque annonce doit posséder un identifiant non vide.")
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Les identifiants d'annonces doivent être uniques.")

    strong_groups: dict[tuple[str, str], list[int]] = defaultdict(list)
    ignored_short_text_rows = 0
    for index, row in enumerate(row_list):
        url_key = normalized_url_key(row.get("url"))
        if url_key:
            strong_groups[("same_url", url_key)].append(index)

        text_key = normalized_text_key(row.get("texte_nettoye"))
        if len(text_key) >= _MIN_TEXT_KEY_LENGTH:
            strong_groups[("same_normalized_text", text_key)].append(index)
        elif text_key:
            ignored_short_text_rows += 1

    disjoint_set = _DisjointSet(len(row_list))
    for indices in strong_groups.values():
        for index in indices[1:]:
            disjoint_set.union(indices[0], index)

    components: dict[int, list[int]] = defaultdict(list)
    for index in range(len(row_list)):
        components[disjoint_set.find(index)].append(index)

    reasons_by_component: dict[int, set[str]] = defaultdict(set)
    hashes_by_component: dict[int, set[str]] = defaultdict(set)
    for (reason, value), indices in strong_groups.items():
        if len(indices) < 2:
            continue
        root = disjoint_set.find(indices[0])
        reasons_by_component[root].add(reason)
        hashes_by_component[root].add(_hash_key(reason, value))

    trace: list[dict[str, Any]] = []
    kept_indices: set[int] = set()
    certain_clusters = 0
    for root, indices in components.items():
        keeper = max(indices, key=lambda index: _keeper_sort_key(row_list[index]))
        kept_indices.add(keeper)
        if len(indices) == 1:
            continue
        certain_clusters += 1
        group_hash = _hash_key("duplicate_group", sorted(identifiers[i] for i in indices))
        reasons = sorted(reasons_by_component[root])
        key_hashes = sorted(hashes_by_component[root])
        for index in indices:
            if index == keeper:
                continue
            trace.append(
                {
                    "groupe_doublon_id": group_hash,
                    "id_conserve": identifiers[keeper],
                    "id_ecarte": identifiers[index],
                    "motifs": "+".join(reasons),
                    "empreintes": "+".join(key_hashes),
                }
            )

    candidate_groups: dict[tuple[str, int, int], list[int]] = defaultdict(list)
    for index in sorted(kept_indices):
        key = characteristic_key(row_list[index])
        if key is not None:
            candidate_groups[key].append(index)

    candidate_clusters = []
    for key, indices in candidate_groups.items():
        if len(indices) < 2:
            continue
        candidate_clusters.append(
            {
                "groupe_candidat_id": _hash_key("candidate_group", key),
                "nombre_annonces": len(indices),
                "ids": [identifiers[index] for index in indices],
                "decision": "review_required",
            }
        )
    candidate_clusters.sort(
        key=lambda group: (-group["nombre_annonces"], group["groupe_candidat_id"])
    )

    total = len(row_list)
    removed = len(trace)
    remaining = total - removed
    report = {
        "phase": "Déduplication",
        "observations_avant": total,
        "observations_supprimees_simulees": removed,
        "observations_restantes_simulees": remaining,
        "perte_pct": round((removed / total * 100) if total else 0.0, 2),
        "groupes_doublons_certains": certain_clusters,
        "candidats_caracteristiques": len(candidate_clusters),
        "lignes_texte_court_ignorees": ignored_short_text_rows,
        "regles_suppression_automatique": ["same_url", "same_normalized_text"],
        "regle_revision_manuelle": "same_neighborhood_price_surface",
        "reference_historique": REFERENCE_COUNTS,
        "ecarts_reference": {
            "observations_avant": total - REFERENCE_COUNTS["observations_avant"],
            "observations_supprimees": removed - REFERENCE_COUNTS["observations_supprimees"],
            "observations_restantes": remaining - REFERENCE_COUNTS["observations_restantes"],
        },
        "candidate_clusters": candidate_clusters,
        "read_only": True,
        "database_modified": False,
        "sensitive_text_exported": False,
        "contacts_exported": False,
    }
    return report, sorted(trace, key=lambda item: (item["groupe_doublon_id"], item["id_ecarte"]))
