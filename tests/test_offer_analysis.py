import unittest
from app.offer_analysis import analyze_offer
from app.search_engine import SearchCandidate, parse_search_description


def peer(i, price, **changes):
    values=dict(identifier=str(i),text=f'Offre {i} avec un repère distinct',property_type='parcelle',neighborhood='Saaba',price_fcfa=price,area_m2=300,age_days=1,document_status='puh')
    values.update(changes)
    return SearchCandidate(**values)


class OfferAnalysisTests(unittest.TestCase):
    def test_better_nearby_offer_has_a_reason_and_does_not_bias_local_prices(self):
        data=[peer(1,3_000_000,neighborhood='Bendogo'),peer(2,4_000_000)]
        analysis,_,results=analyze_offer('Parcelle à Saaba 300 m² prix 5 millions',data)
        self.assertEqual(analysis['nombre_comparables'],1)
        self.assertEqual([r.candidate.identifier for r in results],['2','1'])
        self.assertTrue(results[0].comparison['meme_quartier'])
        self.assertEqual(results[1].comparison['distance_km'],5.0)
        self.assertTrue(results[1].comparison['avantages'])

    def test_no_cheaper_but_undocumented_or_worse_offer(self):
        text='Parcelle à Saaba 300 m² prix 5 millions. PUH disponible. Eau sur place. Électricité sur place. Proche d’une école.'
        data=[peer(1,1_000_000,document_status=None),peer(2,2_000_000),peer(3,6_000_000,text='PUH disponible. Eau sur place. Électricité sur place. Proche d’une école.')]
        _,_,results=analyze_offer(text,data)
        self.assertEqual(results,[])

    def test_complete_nearby_offer_takes_priority_over_incomplete_local_offer(self):
        data=[peer(1,2_000_000),peer(2,3_000_000,neighborhood='Bendogo',text='PUH disponible. Eau sur place. Électricité sur place. Proche d’une école.')]
        _,_,results=analyze_offer('Parcelle à Saaba 300 m² prix 5 millions',data)
        self.assertEqual(results[0].candidate.identifier,'2')

    def test_same_quality_higher_price_is_not_called_better(self):
        _,_,results=analyze_offer('Parcelle à Saaba 300 m² prix 5 millions. PUH.',[peer(1,7_000_000)],preferences='Budget maximum 10 millions')
        self.assertEqual(results,[])

    def test_more_complete_offer_can_cost_more_only_within_budget_and_explained(self):
        data=[peer(1,6_000_000,text='PUH disponible. Eau sur place. Électricité sur place. Proche d’une école.')]
        _,_,results=analyze_offer('Parcelle à Saaba 300 m² prix 5 millions',data,preferences='Budget maximum 7 millions')
        self.assertEqual(len(results),1)
        self.assertTrue(results[0].comparison['compromis'])
        self.assertGreater(results[0].comparison['ecart_prix_m2_pct'],0)
        _,_,limited=analyze_offer('Parcelle à Saaba 300 m² prix 5 millions',data,preferences='Budget maximum 5 millions')
        self.assertEqual(limited,[])

    def test_required_quarter_and_other_criteria_still_apply_to_nearby_results(self):
        data=[peer(1,3_000_000,neighborhood='Bendogo'),peer(2,3_500_000,document_status='attestation_attribution'),peer(3,4_000_000)]
        _,_,results=analyze_offer('Parcelle à Saaba 300 m² prix 5 millions',data,preferences='Uniquement à Saaba avec PUH')
        self.assertEqual([r.candidate.identifier for r in results],['3'])
        _,_,strict=analyze_offer('Parcelle à Saaba 300 m² prix 5 millions',[data[0]],required_fields=frozenset({'quartier'}))
        self.assertEqual(strict,[])

    def test_incomparable_large_far_old_and_over_budget_alternatives_are_excluded(self):
        data=[peer(1,1_000_000,neighborhood='Pabré'),peer(2,1_000_000,neighborhood='Bendogo',area_m2=30000),peer(3,1_000_000,age_days=40),peer(4,6_000_000,neighborhood='Bendogo'),peer(5,3_000_000,neighborhood='Bendogo')]
        _,_,results=analyze_offer('Parcelle à Saaba 300 m² prix 9 millions',data,preferences='Budget maximum 5 millions')
        self.assertEqual([r.candidate.identifier for r in results],['5'])

    def test_summary_uses_simple_french_and_preserves_the_price(self):
        analysis,_,_=analyze_offer('Parcelle à Saaba 300 m² prix 9 millions. APFR déposée.',[peer(1,3_000_000),peer(2,3_500_000),peer(3,4_000_000)])
        self.assertIn('9 000 000 FCFA',analysis['resume'])
        self.assertIn('30 000 FCFA/m²',analysis['resume'])
        self.assertIn('À vérifier',analysis['resume'])
        self.assertNotIn('médiane',analysis['resume'])
        self.assertNotIn('médiane',analysis['comparaison'])

    def test_qualified_rural_homonym_does_not_use_the_urban_map_point(self):
        data=[peer(1,2_000_000,neighborhood='Kossodo')]
        analysis,_,results=analyze_offer('Parcelle au village de Tanghin, commune de Saaba, 300 m² prix 5 millions.',data)
        self.assertEqual(analysis['bien']['quartier'],'Tanghin (Saaba)')
        self.assertFalse(analysis['zone_recherche']['quartiers_proches_inclus'])
        self.assertEqual(results,[])

    def test_overpriced_publication_is_compared_to_three_peers(self):
        data=[peer(1,3_000_000),peer(2,3_600_000),peer(3,4_200_000)]
        analysis,criteria,alternatives=analyze_offer('Parcelle à Saaba 300 m² prix 9 millions FCFA. APFR déposée.',data)
        self.assertIn('Prix élevé',analysis['verdict'])
        self.assertEqual(analysis['nombre_comparables'],3)
        self.assertEqual(analysis['mediane_prix_m2'],12_000)
        self.assertEqual(analysis['qualite']['document_etat'],'en_cours')
        self.assertEqual(len(alternatives),3)
        self.assertIsNone(criteria.document_status)
        replay=parse_search_description(criteria.description)
        self.assertEqual(replay.neighborhood,'Saaba')
        self.assertEqual(replay.area_m2,300)

    def test_rural_hectares_and_other_zones_are_not_comparables(self):
        data=[peer(1,3_000_000,area_m2=30000,text='Terrain agricole de trois hectares'),peer(2,3_000_000,neighborhood='Karpala')]
        analysis,_,_=analyze_offer('Parcelle à Saaba 300 m² prix 9 millions',data)
        self.assertEqual(analysis['nombre_comparables'],0)
        self.assertIsNone(analysis['ecart_mediane_pct'])
        self.assertIn('non confirmée',analysis['verdict'])

    def test_subject_and_republications_do_not_bias_the_median(self):
        text='Parcelle à Saaba de 300 m² au prix de 9 millions avec PUH'
        data=[peer(1,9_000_000,text=text),peer(2,9_000_000,text=text),peer(3,4_000_000)]
        analysis,_,alternatives=analyze_offer(text,data)
        self.assertEqual(analysis['nombre_comparables'],1)
        self.assertEqual([r.candidate.identifier for r in alternatives],['3'])

    def test_missing_surface_prevents_price_verdict(self):
        analysis,_,_=analyze_offer('Parcelle à Saaba prix 5 millions FCFA',[])
        self.assertIsNone(analysis['bien']['prix_m2_fcfa'])
        self.assertIn('impossible',analysis['verdict'])

    def test_real_user_budget_filters_alternatives(self):
        data=[peer(1,3_000_000),peer(2,7_000_000)]
        analysis,criteria,alternatives=analyze_offer('Parcelle à Saaba 300 m² prix 9 millions',data,preferences='Budget maximum 6 millions pour une parcelle à Saaba')
        self.assertEqual(criteria.price_fcfa,6_000_000)
        self.assertTrue(criteria.price_is_maximum)
        self.assertEqual([r.candidate.identifier for r in alternatives],['1'])
        self.assertEqual(analysis['bien']['prix_fcfa'],9_000_000)

    def test_unit_price_in_publication_is_not_mistaken_for_total_price(self):
        analysis,_,_=analyze_offer('Parcelle à Saaba, superficie 300 m². Prix 15 000 FCFA/m².',[])
        self.assertEqual(analysis['bien']['prix_fcfa'],4_500_000)
        self.assertEqual(analysis['bien']['prix_m2_fcfa'],15_000)

    def test_unknown_literal_neighborhood_is_not_replaced_by_city(self):
        data=[peer(1,3_000_000,text='Parcelle à Roumtenga (Songdin)',neighborhood='Ouagadougou'),peer(2,2_000_000,neighborhood='Karpala')]
        analysis,criteria,alternatives=analyze_offer('Parcelle à ROUMTENGA (Songdin), 300 m², prix 3 500 000 FCFA',data)
        self.assertEqual(analysis['bien']['quartier'],'Roumtenga')
        self.assertEqual(analysis['bien']['prix_fcfa'],3_500_000)
        self.assertEqual(analysis['bien']['prix_m2_fcfa'],11_666.67)
        self.assertEqual([r.candidate.identifier for r in alternatives],['1'])

    def test_other_neighborhoods_are_not_silent_alternatives(self):
        data=[peer(1,1_000_000,neighborhood='Karpala')]
        _,_,alternatives=analyze_offer('Parcelle à Saaba 300 m² à 9 millions FCFA',data)
        self.assertEqual(alternatives,[])

    def test_city_only_is_not_enough_for_local_comparison(self):
        data=[peer(1,1_000_000,neighborhood='Ouagadougou')]
        analysis,_,alternatives=analyze_offer('Parcelle à Ouagadougou 300 m² à 9 millions FCFA',data)
        self.assertEqual(analysis['nombre_comparables'],0)
        self.assertEqual(alternatives,[])

    def test_replayed_budget_preserves_all_digits(self):
        _,criteria,_=analyze_offer('Parcelle à Saaba 300 m² à 9 millions FCFA',[],preferences='Budget maximum 6 millions')
        self.assertEqual(parse_search_description(criteria.description).price_fcfa,6_000_000)

    def test_common_price_formats_preserve_millions(self):
        for amount in ['3 500 000', '3\u202f500\u202f000', '3.500.000', '3 millions 500']:
            analysis,_,_=analyze_offer('Parcelle à Saaba 300 m² prix '+amount+' FCFA',[])
            self.assertEqual(analysis['bien']['prix_fcfa'],3_500_000)
