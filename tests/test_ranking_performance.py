"""Preserve deduplication results while avoiding unrelated pair comparisons."""
import random
import unittest
from dataclasses import replace
from unittest.mock import patch
from app import search_engine as engine


class RankingPerformanceTests(unittest.TestCase):
    def test_results_match_original_pairwise_deduplication(self):
        rng = random.Random(42)
        rows = [
            engine.SearchCandidate(
                identifier=str(i),
                text=rng.choice(["Parcelle à Saaba proche école", "Terrain à Saaba près du marché", "Parcelle à Karpala"]),
                neighborhood=rng.choice(["Saaba", "SAABA", None, ""]),
                property_type=rng.choice(["parcelle", None]),
                price_fcfa=rng.choice([None, 5000000, 6000000]),
                area_m2=rng.choice([None, 250, 300]),
                contact=rng.choice([None, "70123456", "+226 70 12 34 56"]),
            ) for i in range(120)
        ]
        rows.extend([replace(rows[3], text="Un autre texte"), rows[7]])
        unique = []
        for candidate in rows:
            if not any(engine._same_announcement(candidate, other) for other in unique):
                unique.append(candidate)
        criteria = engine.SearchCriteria(description="parcelle")
        self.assertEqual(
            engine.rank_candidates(criteria, rows, limit=200),
            engine.rank_candidates(criteria, unique, limit=200),
        )

    def test_distinct_prices_do_not_trigger_quadratic_duplicate_checks(self):
        rows = [engine.SearchCandidate(
            identifier=str(i), text="Parcelle à Saaba",
            price_fcfa=5000000 + i, area_m2=300,
            property_type="parcelle", neighborhood="Saaba",
        ) for i in range(2000)]
        with patch.object(engine, "_same_announcement", wraps=engine._same_announcement) as check:
            engine.rank_candidates(engine.SearchCriteria(description="parcelle"), rows, limit=10)
        self.assertLess(check.call_count, 2000)


if __name__ == "__main__":
    unittest.main()
