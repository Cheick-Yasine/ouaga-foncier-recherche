"""Régression : ne pas recompiler le référentiel pour chaque publication."""
import re
import unittest
from unittest.mock import patch

from app.neighborhoods import _compiled_pattern, resolve_neighborhood


class NeighborhoodBatchTests(unittest.TestCase):
    def test_batch_reuses_patterns_and_keeps_location_rules(self):
        _compiled_pattern.cache_clear()
        with patch('app.neighborhoods.re.compile', wraps=re.compile) as compile_pattern:
            for i in range(30):
                assert resolve_neighborhood(f'Parcelle en vente à Karpala, offre {i}', 'Saaba').canonical == 'Karpala'
            # A full first pass needs about 550 patterns; previously 30 ads
            # rebuilt more than 15,000 expressions, saturating the free worker.
            self.assertLess(compile_pattern.call_count, 700)
            assert resolve_neighborhood('Parcelle à Yako, contact à Ouaga', 'Ouagadougou').canonical is None
            assert resolve_neighborhood('Parcelle à Gounghin Sud', 'Ouagadougou').canonical == 'Gounghin Sud'
