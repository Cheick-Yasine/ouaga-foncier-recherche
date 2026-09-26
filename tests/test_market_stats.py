from datetime import datetime, timedelta, timezone
from dataclasses import replace
import unittest

from app.market_stats import neighborhood_trends, publication_time, summarize_market
from app.search_engine import SearchCandidate


class MarketStatsTests(unittest.TestCase):
    now = datetime(2026, 9, 6, 12, tzinfo=timezone.utc)

    def candidate(self, identifier, **changes):
        base = SearchCandidate(identifier, 'Parcelle en vente à Karpala', neighborhood='Karpala', property_type='parcelle', price_fcfa=3_000_000, area_m2=300, publication_label=(self.now-timedelta(days=5)).isoformat())
        return replace(base, **changes)


    def test_unix_publication_timestamps_are_supported(self):
        seconds = publication_time('1789738217')
        milliseconds = publication_time('1789738217000')
        expected = datetime(2026, 9, 18, 13, 30, 17, tzinfo=timezone.utc)
        self.assertEqual(seconds, expected)
        self.assertEqual(milliseconds, expected)

    def test_mean_counts_and_top_quarter_share_same_eligible_pool(self):
        rows = [self.candidate('a'), self.candidate('b', price_fcfa=6_000_000), self.candidate('no-price', price_fcfa=None)]
        rows += [
            self.candidate('surroundings', text='Terrain à Saaba', neighborhood='Saaba'),
            self.candidate('variant', text='Parcelle en vente à Dayoubsi', neighborhood='Dayoubsi'),
            self.candidate('outside', text='Terrain à Bobo-Dioulasso', neighborhood='Bobo-Dioulasso'),
            self.candidate('rent', text='Parcelle en location à Karpala'),
            self.candidate('future', publication_label=(self.now+timedelta(days=1)).isoformat()),
            self.candidate('old', publication_label=(self.now-timedelta(days=31)).isoformat()),
            self.candidate('unknown-date', publication_label='Il y a 2 h'),
        ]
        stats = summarize_market(rows, now=self.now)
        self.assertEqual(stats['annonces_30_jours'], 5)
        self.assertEqual(stats['prix_m2_moyen_fcfa'], 12_500)
        self.assertEqual(stats['annonces_avec_prix_m2'], 4)
        self.assertEqual(stats['quartier_le_plus_represente'], 'Karpala')
        self.assertEqual(stats['annonces_quartier_principal'], 3)
        self.assertEqual(stats['perimetre'], 'Ouagadougou et environs')

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



def test_neighborhood_top_five_is_recomputed_for_selected_period() -> None:
    now = datetime(2026, 9, 19, 12, tzinfo=timezone.utc)

    def row(identifier, neighborhood, days_ago):
        return SearchCandidate(
            identifier=identifier,
            text=f"Parcelle en vente à {neighborhood}",
            neighborhood=neighborhood,
            property_type="parcelle",
            publication_label=(now - timedelta(days=days_ago)).isoformat(),
        )

    rows = [
        *[
            row(f"old-{index}", "Karpala", 20)
            for index in range(10)
        ],
        *[
            row(f"saaba-{index}", "Saaba", index % 3)
            for index in range(6)
        ],
        *[
            row(f"bassinko-{index}", "Bassinko", index % 2)
            for index in range(4)
        ],
        row("boassa-1", "Boassa", 1),
        row("komsilga-1", "Komsilga", 2),
        row("kouba-1", "Kouba", 3),
        row("tanghin-1", "Tanghin", 4),
    ]

    recent = neighborhood_trends(rows, now=now, period="7d", aggregation="day")
    recent_names = [
        item["nom"]
        for item in recent["types"]["tous"]["quartiers"]
    ]
    assert recent_names[0] == "Saaba"
    assert "Karpala" not in recent_names
    assert len(recent_names) == 5

    maximum = neighborhood_trends(rows, now=now, period="max", aggregation="day")
    max_names = [
        item["nom"]
        for item in maximum["types"]["tous"]["quartiers"]
    ]
    assert max_names[0] == "Karpala"


def test_neighborhood_week_aggregation_groups_selected_period() -> None:
    now = datetime(2026, 9, 19, 12, tzinfo=timezone.utc)
    rows = [
        SearchCandidate(
            identifier=f"saaba-{days_ago}",
            text="Parcelle en vente à Saaba",
            neighborhood="Saaba",
            property_type="parcelle",
            publication_label=(now - timedelta(days=days_ago)).isoformat(),
        )
        for days_ago in (0, 1, 6, 7, 10, 13)
    ]

    trends = neighborhood_trends(
        rows,
        now=now,
        period="14d",
        aggregation="week",
    )
    points = trends["types"]["tous"]["quartiers"][0]["points"]

    assert trends["agregation"] == "week"
    assert trends["periode"] == "14d"
    assert sum(point["annonces"] for point in points) == 6
    assert all(point["debut"] <= point["fin"] for point in points)



def test_weekly_market_exposes_mean_median_and_values_for_expert_mode() -> None:
    now = datetime(2026, 9, 6, 12, tzinfo=timezone.utc)
    rows = [
        SearchCandidate(
            identifier=f"row-{index}",
            text="Parcelle en vente à Karpala",
            neighborhood="Karpala",
            property_type="parcelle",
            price_fcfa=price,
            area_m2=100,
            publication_label=(now - timedelta(days=8)).isoformat(),
        )
        for index, price in enumerate((1_000_000, 2_000_000, 9_000_000))
    ]

    stats = summarize_market(rows, now=now)
    populated = next(
        week["types"]["tous"]
        for week in stats["semaines"]
        if week["types"]["tous"]["prix_renseignes"]
    )

    assert populated["prix_m2_moyen"] == 40_000
    assert populated["prix_m2_mediane"] == 20_000
    assert populated["prix_m2_values"] == [10_000, 20_000, 90_000]
    assert populated["prix_m2"] == populated["prix_m2_moyen"]


def test_neighborhood_periods_accept_three_and_five_year_windows() -> None:
    now = datetime(2026, 9, 19, 12, tzinfo=timezone.utc)
    rows = [
        SearchCandidate(
            identifier="recent",
            text="Parcelle en vente à Saaba",
            neighborhood="Saaba",
            property_type="parcelle",
            publication_label=(now - timedelta(days=700)).isoformat(),
        ),
        SearchCandidate(
            identifier="older",
            text="Parcelle en vente à Karpala",
            neighborhood="Karpala",
            property_type="parcelle",
            publication_label=(now - timedelta(days=1400)).isoformat(),
        ),
    ]

    three_years = neighborhood_trends(
        rows,
        now=now,
        period="3y",
        aggregation="week",
    )
    five_years = neighborhood_trends(
        rows,
        now=now,
        period="5y",
        aggregation="week",
    )

    assert three_years["periode"] == "3y"
    assert [item["nom"] for item in three_years["types"]["tous"]["quartiers"]] == ["Saaba"]
    assert five_years["periode"] == "5y"
    assert {item["nom"] for item in five_years["types"]["tous"]["quartiers"]} == {
        "Saaba",
        "Karpala",
    }
