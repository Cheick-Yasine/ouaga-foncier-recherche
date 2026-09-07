"""Exclusions avant classement : pas de location ni d'élargissement caché."""
from dataclasses import replace
from types import SimpleNamespace
import unittest

from app.assistant_constraints import conversation_city_only, respect_search_scope
from app.listing_scope import sale_eligible, within_ouagadougou, facebook_publication_url
from app.search_engine import SearchCandidate, parse_search_description, rank_candidates


class ListingScopeTests(unittest.TestCase):
    def test_rentals_mixed_listings_and_requests_are_excluded(self):
        for text in (
            'Parcelle à louer à Karpala, 100 000 FCFA',
            'Terrain en location à Kossodo',
            'Maison en vente ou en location, loyer 100 000',
            'Agence vente et location : parcelle disponible à Karpala',
            'Parcelle à vendre, 3 mois de caution',
            'Maison 100 000 FCFA/mois',
            'Je cherche une parcelle à Karpala',
            'Parcelle déjà vendue à Karpala',
            'Terrain pas en vente',
        ):
            with self.subTest(text=text): self.assertFalse(sale_eligible(text))
        self.assertTrue(sale_eligible('Parcelle à vendre à Karpala, pas de location.'))

    def test_city_scope_uses_map_and_rejects_unknown_or_rural_homonyms(self):
        for name in ('Karpala', 'Kossodo', 'Ouaga 2000', 'Tanghin', 'Ouagadougou'):
            with self.subTest(name=name): self.assertTrue(within_ouagadougou('Parcelle à '+name, name))
        for name in ('Saaba', 'Gampela', 'Pabré', 'Yako', 'Koudière', 'Zone inconnue'):
            with self.subTest(name=name): self.assertFalse(within_ouagadougou('Parcelle à '+name, 'Ouagadougou'))
        self.assertFalse(within_ouagadougou('Parcelle à Tanghin, commune de Saaba', 'Tanghin'))
        self.assertFalse(within_ouagadougou('Parcelle en commune de Komsilga', 'Ouagadougou'))

    def test_hard_exclusions_precede_price_and_completeness(self):
        urban = SearchCandidate('urban', 'Parcelle en vente à Karpala', neighborhood='Karpala', property_type='parcelle', price_fcfa=8_000_000, area_m2=300)
        outer = replace(urban, identifier='outer', text='Parcelle en vente à Saaba', neighborhood='Saaba', price_fcfa=1_000_000)
        rental = replace(urban, identifier='rent', text='Parcelle à louer à Karpala', price_fcfa=20_000)
        criteria = parse_search_description('Bonne affaire : parcelle uniquement à Ouagadougou, budget maximum 10 millions FCFA')
        ranked = rank_candidates(criteria, [outer, rental, urban])
        self.assertEqual([r.candidate.identifier for r in ranked], ['urban'])
        expanded = parse_search_description('Parcelle à Ouagadougou et dans ses environs')
        self.assertFalse(expanded.city_only)
        self.assertEqual({r.candidate.identifier for r in rank_candidates(expanded, [urban, outer, rental])}, {'urban', 'outer'})

    def test_followup_keeps_city_until_user_changes_it(self):
        history = [SimpleNamespace(role='user', content='Une parcelle seulement à Ouaga'), SimpleNamespace(role='assistant', content='Vous pourriez aller à Saaba.')]
        self.assertTrue(conversation_city_only('Avec une école', history))
        self.assertFalse(conversation_city_only('Ajoute aussi les environs', history))
        self.assertFalse(conversation_city_only('Cherche plutôt à Saaba', history))
        self.assertFalse(conversation_city_only('Cherche à Ouaga 2000', history))
        self.assertFalse(parse_search_description('Seulement des parcelles à Ouaga et dans ses environs').city_only)

    def test_guard_filters_mcp_rows_before_advice(self):
        payload={'results':[{'id':'city','quartier':'Karpala','description':'Parcelle à Karpala'}, {'id':'outer','quartier':'Saaba'}, {'id':'rent','quartier':'Karpala','description':'Terrain en location'}]}
        result=respect_search_scope(payload, True, 'Uniquement à Ouagadougou')
        self.assertEqual([r['id'] for r in result['results']], ['city'])
        self.assertEqual(result['nombre_resultats'], 1)
        self.assertTrue(result['criteres']['ouagadougou_uniquement'])

    def test_source_links_are_original_facebook_urls(self):
        url='https://www.facebook.com/groups/123/posts/456/?ref=share'
        self.assertEqual(facebook_publication_url(url), url)
        for url in ('javascript:alert(1)', 'https://facebook.com.evil.test/posts/1', 'https://facebook.com@evil.test/posts/1', 'https://facebook.com/l.php?u=https://evil.test', 'https://example.test/?annonce=1', 'https://facebook.com/'):
            with self.subTest(url=url): self.assertIsNone(facebook_publication_url(url))
