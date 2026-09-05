import unittest
from app.offer_analysis import analyze_offer
from app.search_engine import SearchCandidate, parse_search_description


def peer(i, price, **changes):
    values=dict(identifier=str(i),text=f'Offre {i} avec un repère distinct',property_type='parcelle',neighborhood='Saaba',price_fcfa=price,area_m2=300,age_days=1)
    values.update(changes)
    return SearchCandidate(**values)


class OfferAnalysisTests(unittest.TestCase):
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
