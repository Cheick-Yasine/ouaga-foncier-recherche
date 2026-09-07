from datetime import datetime, timedelta, timezone
from dataclasses import replace
import unittest

from app.market_stats import summarize_market
from app.search_engine import SearchCandidate


class MarketStatsTests(unittest.TestCase):
    now = datetime(2026, 9, 6, 12, tzinfo=timezone.utc)

    def candidate(self, identifier, **changes):
        base = SearchCandidate(identifier, 'Parcelle en vente à Karpala', neighborhood='Karpala', property_type='parcelle', price_fcfa=3_000_000, area_m2=300, publication_label=(self.now-timedelta(days=5)).isoformat())
        return replace(base, **changes)

    def test_mean_counts_and_top_quarter_share_same_eligible_pool(self):
        rows = [self.candidate('a'), self.candidate('b', price_fcfa=6_000_000), self.candidate('no-price', price_fcfa=None)]
        rows += [self.candidate('outer', text='Terrain à Saaba', neighborhood='Saaba'), self.candidate('rent', text='Parcelle en location à Karpala'), self.candidate('future', publication_label=(self.now+timedelta(days=1)).isoformat()), self.candidate('old', publication_label=(self.now-timedelta(days=31)).isoformat()), self.candidate('unknown-date', publication_label='Il y a 2 h')]
        stats = summarize_market(rows, now=self.now)
        self.assertEqual(stats['annonces_30_jours'], 3)
        self.assertEqual(stats['prix_m2_moyen_fcfa'], 15_000)
        self.assertEqual(stats['annonces_avec_prix_m2'], 2)
        self.assertEqual(stats['quartier_le_plus_represente'], 'Karpala')
        self.assertEqual(stats['annonces_quartier_principal'], 3)

    def test_known_publication_date_takes_precedence_over_collection(self):
        rows=[self.candidate('recent', collected_at='2020-01-01T00:00:00Z'), self.candidate('old', publication_label='2020-01-01T00:00:00Z', collected_at=self.now.isoformat())]
        self.assertEqual(summarize_market(rows, now=self.now)['annonces_30_jours'], 1)

    def test_duplicate_publication_not_counted_twice(self):
        rows=[self.candidate('a', url='https://facebook.com/posts/1'), self.candidate('b', url='https://facebook.com/posts/1')]
        self.assertEqual(summarize_market(rows, now=self.now)['annonces_30_jours'], 1)

    def test_empty_values_are_not_invented(self):
        stats=summarize_market([], now=self.now)
        self.assertEqual(stats['annonces_30_jours'], 0)
        self.assertIsNone(stats['prix_m2_moyen_fcfa'])
        self.assertIsNone(stats['quartier_le_plus_represente'])

    def test_nonfinite_prices_and_zero_area_do_not_enter_mean(self):
        rows=[self.candidate('a', area_m2=0), self.candidate('b', price_fcfa=float('nan')),self.candidate('c', price_fcfa=float('inf'))]
        stats=summarize_market(rows, now=self.now)
        self.assertEqual(stats['annonces_30_jours'], 3)
        self.assertEqual(stats['annonces_avec_prix_m2'], 0)
        self.assertIsNone(stats['prix_m2_moyen_fcfa'])
