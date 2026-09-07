import unittest
from unittest.mock import patch

from app.neighborhood_geo import distance_km, location_for, neighborhood_relation


class NeighborhoodGeoTests(unittest.TestCase):
    def test_actual_nearby_points_have_plausible_distances(self):
        self.assertAlmostEqual(distance_km('Saaba', 'Gampela'), 8.0, delta=.1)
        self.assertAlmostEqual(distance_km('Bassinko', 'Yagma'), 3.2, delta=.1)
        self.assertAlmostEqual(distance_km('Gampela', 'Saaba'), distance_km('Saaba', 'Gampela'))

    def test_nearby_relation_is_explicit_and_links_to_map(self):
        relation = neighborhood_relation('Saaba', 'Bendogo')
        self.assertFalse(relation['meme_quartier'])
        self.assertEqual(relation['distance_km'], 5.0)
        self.assertEqual(relation['quartier_origine'], 'Saaba')
        self.assertIn('ligne_droite', relation['distance_type'])
        self.assertIn('openstreetmap.org', relation['carte_url'])

    def test_same_neighborhood_does_not_claim_zero_distance_between_plots(self):
        for a, b in [('Saaba', 'saaba'), ('Cité An III', 'Cité An 3'), ('Roumtenga', 'ROUMTENGA')]:
            relation = neighborhood_relation(a, b)
            self.assertTrue(relation['meme_quartier'])
            self.assertIsNone(relation['distance_km'])

    def test_unknown_broad_or_distant_zone_is_never_assumed_nearby(self):
        for a, b in [('Roumtenga', 'Saaba'), ('Ouagadougou', 'Saaba'), ('Centre Ville', 'Koulouba'), ('Saaba', 'Pabré'), ('Saaba', None), ('Saaba village inconnu', 'Saaba')]:
            self.assertIsNone(neighborhood_relation(a, b))
        self.assertIsNone(distance_km('Roumtenga', 'Saaba'))

    def test_urban_homonyms_are_not_confused_with_farther_villages(self):
        tanghin = location_for('Tanghin')
        self.assertEqual(tanghin['source_id'], 2354986)
        self.assertGreater(tanghin['latitude'], 12.39)
        self.assertEqual(location_for('Kossodo')['source_id'], 2359017)
        self.assertIsNone(location_for('Sabtenga'))  # Two villages: unresolved.

    def test_radius_filter_uses_unrounded_distance(self):
        with patch('app.neighborhood_geo.distance_km', return_value=8.04):
            self.assertIsNone(neighborhood_relation('Saaba', 'Gampela'))

    def test_lookup_does_not_expose_mutable_cached_data(self):
        point = location_for('Saaba')
        point['latitude'] = 0
        self.assertGreater(location_for('Saaba')['latitude'], 12)


if __name__ == '__main__':
    unittest.main()
