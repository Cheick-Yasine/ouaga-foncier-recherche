"""Régressions sur les informations qui changent une recommandation."""
import unittest
from dataclasses import replace

from app.offer_quality import offer_quality
from app.search_engine import SearchCandidate, SearchCriteria, parse_search_description, rank_candidates, score_candidate


def offer(identifier='x', **changes):
    values = dict(identifier=identifier,text='Parcelle à Saaba',property_type='parcelle',neighborhood='Saaba',price_fcfa=5_000_000,area_m2=300)
    values.update(changes)
    return SearchCandidate(**values)


class OfferQualityTests(unittest.TestCase):
    def test_deposited_apfr_is_not_available(self):
        q=offer_quality(offer(text='APFR déjà déposée. Eau à proximité.'))
        self.assertEqual(q['document_etat'],'en_cours')
        self.assertEqual(q['eau_etat'],'proximite')
        self.assertLess(q['indices']['document'],.2)

    def test_negated_utilities_and_documents_get_no_bonus(self):
        q=offer_quality(offer(text='Sans eau ni électricité. Sans documents.',viability='eau_et_electricite',document_status='apfr'))
        self.assertEqual(q['indices']['document'],0)
        self.assertEqual(q['indices']['viabilite'],0)
        self.assertEqual(q['atouts'],[])

    def test_available_utilities_do_not_inherit_nearby_road(self):
        q=offer_quality(offer(text='Attestation disponible. Eau et électricité disponibles. Proche du goudron et non loin du CSPS.'))
        self.assertEqual(q['indices']['viabilite'],1)
        self.assertEqual(q['document_etat'],'annonce_disponible')
        self.assertEqual(len(q['proximites']),2)

    def test_pending_document_fails_required_document(self):
        c=SearchCriteria(description='APFR obligatoire',document_status='apfr',required_fields=frozenset({'statut_document'}))
        self.assertIsNone(score_candidate(c,offer(text='APFR en cours',document_status='apfr')))

    def test_negated_utilities_fail_required_viability(self):
        c=SearchCriteria(description='Avec eau obligatoire',viability='eau',required_fields=frozenset({'viabilite'}))
        self.assertIsNone(score_candidate(c,offer(text='Sans eau',viability='eau')))

    def test_generic_attestation_accepts_specific_attestation(self):
        c=SearchCriteria(description='Avec attestation obligatoire',document_status='attestation_non_precisee',required_fields=frozenset({'statut_document'}))
        self.assertIsNotNone(score_candidate(c,offer(text='Attestation de possession disponible',document_status='attestation_possession')))

    def test_documented_equipped_offer_can_beat_cheaper_bare_offer(self):
        c=parse_search_description('Bonne affaire parcelle à Saaba de 300 m², budget maximum 6 millions')
        bare=offer('bare',text='Parcelle nue à Saaba',price_fcfa=4_000_000)
        rich=offer('rich',text='Attestation disponible. Eau et électricité disponibles. Proche du goudron et non loin du CSPS.',price_fcfa=5_000_000)
        self.assertEqual(rank_candidates(c,[bare,rich])[0].candidate.identifier,'rich')

    def test_identical_quality_prefers_lower_unit_price(self):
        c=parse_search_description('Bonne affaire parcelle à Saaba de 300 m²')
        a=offer('a',text='PUH disponible. Eau et électricité disponibles.',price_fcfa=5_000_000)
        b=offer('b',text=a.text,price_fcfa=6_000_000)
        self.assertEqual(rank_candidates(c,[b,a])[0].candidate.identifier,'a')

    def test_unspecified_good_deal_prefers_small_parcels(self):
        c=parse_search_description('Une bonne affaire budget maximum 6 millions')
        rural=offer('rural',text='Terrain agricole de trois hectares en bas fond',price_fcfa=3_000_000,area_m2=30000)
        parcel=offer('parcel',text='PUH disponible. Eau et électricité disponibles.',price_fcfa=5_000_000)
        self.assertEqual(rank_candidates(c,[rural,parcel])[0].candidate.identifier,'parcel')

    def test_budget_stays_hard_even_for_full_documentation(self):
        c=parse_search_description('Bonne affaire budget maximum 6 millions')
        expensive=offer('expensive',text='PUH disponible. Eau et électricité disponibles.',price_fcfa=7_000_000)
        self.assertEqual(rank_candidates(c,[expensive]),[])

    def test_decimal_millions_and_grouped_area(self):
        c=parse_search_description('Parcelle de 30 000 m² pour 6,5 millions FCFA')
        self.assertEqual(c.price_fcfa,6_500_000)
        self.assertEqual(c.area_m2,30_000)
        self.assertEqual(parse_search_description('Parcelle de 300 m² à 6.000.000 FCFA').price_fcfa,6_000_000)

    def test_ancillary_document_is_not_a_delivered_title(self):
        q=offer_quality(offer(text='Documents : récépissé de dépôt et croquis'))
        self.assertEqual(q['document_etat'],'piece_annexe')
        self.assertEqual(q['document'],'recepisse')

    def test_future_water_does_not_get_availability_points(self):
        q=offer_quality(offer(text='Eau et électricité prévues, raccordement en cours'))
        self.assertEqual(q['indices']['viabilite'],0)
