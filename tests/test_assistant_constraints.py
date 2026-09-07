import unittest
from types import SimpleNamespace

from app.assistant_constraints import conversation_budget, budget_description, respect_search_budget
from app.search_engine import parse_search_description


def message(role, content):
    return SimpleNamespace(role=role, content=content)


class AssistantConstraintsTests(unittest.TestCase):
    def test_original_ten_million_budget_survives_a_twenty_million_rewrite(self):
        budget=conversation_budget('Trouve-moi une bonne affaire : une parcelle à Ouagadougou ou dans ses environs, budget maximum 10 millions FCFA.',[])
        description=budget_description('Parcelle à Saaba, budget maximum 20 millions FCFA, avec un PUH',budget)
        criteria=parse_search_description(description)
        self.assertEqual(criteria.price_fcfa,10_000_000)
        self.assertTrue(criteria.price_is_maximum)
        self.assertNotIn('20 millions',description)
        self.assertEqual(criteria.neighborhood,'Saaba')
        self.assertEqual(criteria.document_status,'puh')

    def test_followup_keeps_user_budget_and_ignores_assistant_amounts(self):
        history=[message('user','Budget maximum 10 millions'),message('assistant','Voici une parcelle à 20 millions, budget maximum 20 millions')]
        self.assertEqual(conversation_budget('Privilégie les documents disponibles',history),10_000_000)
        self.assertEqual(conversation_budget('Mon budget maximum passe à 8 millions',history),8_000_000)

    def test_latest_user_budget_takes_precedence(self):
        history=[message('user','Budget maximum 6 millions'),message('user','Finalement mon budget est de 9 millions')]
        self.assertEqual(conversation_budget('Seulement à Saaba',history),9_000_000)

    def test_seller_price_or_quoted_budget_is_not_the_buyer_budget(self):
        history=[message('user','Budget maximum 6 millions')]
        self.assertEqual(conversation_budget('Voici l’annonce : Parcelle, budget maximum 20 millions',history),6_000_000)
        self.assertIsNone(conversation_budget('Parcelle à Saaba 300 m² prix 20 millions. Est-ce une bonne affaire ?',[]))

    def test_explicit_budget_removal_does_not_restore_an_old_limit(self):
        history=[message('user','Budget maximum 6 millions')]
        self.assertIsNone(conversation_budget('Cherche sans limite de budget',history))
        history.append(message('user','Supprime la limite de budget'))
        self.assertIsNone(conversation_budget('Avec un PUH',history))

    def test_decimal_and_spaced_amounts_keep_their_value(self):
        for text in ['Budget maximum 6,5 millions','Mon budget est de 6 500 000 FCFA','Budget 6.500.000 FCFA']:
            budget=conversation_budget(text,[])
            self.assertEqual(budget,6_500_000)
            self.assertEqual(parse_search_description(budget_description('Parcelle à Saaba',budget)).price_fcfa,budget)

    def test_over_budget_or_unverifiable_prices_cannot_reach_the_advice_or_table(self):
        rows=[{'id':str(i),'prix_fcfa':p} for i,p in enumerate([20_000_000,10_000_000,9_000_000,None,0,-1,float('nan'),float('inf'),True,'inconnu'])]
        original={'results':rows,'nombre_resultats':10,'criteres':{'quartier':'Saaba','prix_fcfa':20_000_000}}
        safe=respect_search_budget(original,10_000_000,'Budget maximum 10000000 FCFA. Parcelle à Saaba')
        self.assertEqual([r['prix_fcfa'] for r in safe['results']],[10_000_000,9_000_000])
        self.assertEqual(safe['nombre_resultats'],2)
        self.assertEqual(safe['criteres']['prix_fcfa'],10_000_000)
        self.assertTrue(safe['criteres']['prix_est_un_maximum'])
        self.assertEqual(safe['criteres']['quartier'],'Saaba')
        self.assertEqual(len(original['results']),10)

    def test_no_offer_within_budget_stays_an_empty_search(self):
        safe=respect_search_budget({'results':[{'prix_fcfa':20_000_000}]},10_000_000,'Budget maximum 10000000 FCFA')
        self.assertEqual(safe['results'],[])
        self.assertEqual(safe['nombre_resultats'],0)


if __name__=='__main__':
    unittest.main()
