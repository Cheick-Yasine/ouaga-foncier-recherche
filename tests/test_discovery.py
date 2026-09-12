from datetime import datetime, timedelta, timezone
from dataclasses import replace
from types import SimpleNamespace

from app.assistant_constraints import conversation_numeric_request, target_price_description, area_description
from app.market_stats import summarize_market
from app.search_engine import SearchCandidate, parse_search_description, rank_candidates


def parcel(identifier, price, area=300):
    return SearchCandidate(identifier, 'Parcelle en vente à Karpala', property_type='parcelle', neighborhood='Karpala', price_fcfa=price, area_m2=area)


def test_fifty_million_search_prefers_nearby_amounts_but_keeps_ceiling():
    rows=[parcel('far',27000000),parcel('near',48000000),parcel('over',51000000)]
    result=rank_candidates(parse_search_description('Parcelle à Karpala budget maximum 50 millions FCFA'), rows)
    assert [r.candidate.identifier for r in result] == ['near','far']
    result=rank_candidates(parse_search_description('Parcelle à Karpala prix souhaité 50 millions FCFA'), rows)
    assert result[0].candidate.identifier == 'over'


def test_latest_user_price_overrides_old_ceiling_without_model_reinterpretation():
    history=[SimpleNamespace(role='user',content='Budget maximum 10 millions'),SimpleNamespace(role='assistant',content='Budget maximum 5 millions')]
    request=conversation_numeric_request('Prix souhaité autour de 50 millions FCFA',history,'prix')
    assert request.price_fcfa == 50000000 and not request.price_is_maximum
    description=target_price_description('Parcelle à Karpala budget maximum 27 millions FCFA',request.price_fcfa)
    parsed=parse_search_description(description)
    assert parsed.price_fcfa == 50000000 and not parsed.price_is_maximum
    assert conversation_numeric_request('Voici l’annonce : parcelle prix 100 millions',[], 'prix') is None


def test_surface_range_filters_both_edges_and_preserves_independent_budget():
    request=parse_search_description('Parcelle budget maximum 50 millions FCFA. Superficie entre 300 et 499 m².')
    assert request.price_fcfa == 50000000
    assert (request.area_min_m2,request.area_max_m2)==(300,499)
    rows=[parcel('small',40000000,299),parcel('low',40000000,300),parcel('high',40000000,499),parcel('large',40000000,500)]
    assert {r.candidate.identifier for r in rank_candidates(request,rows)} == {'low','high'}
    description=area_description('Superficie souhaitée 200 m².',request)
    assert parse_search_description(description).area_min_m2 == 300
    request=parse_search_description('Superficie minimum 10000 m². Terrain prix 50 millions FCFA')
    assert request.area_min_m2 == 10000 and request.area_max_m2 is None
    exact=parse_search_description('Superficie souhaitée 350 m²')
    assert parse_search_description(area_description('Parcelle de 200 m² à Karpala',exact)).area_m2 == 350


def test_four_complete_weeks_use_publication_boundaries_and_null_prices():
    now=datetime(2026,9,12,12,tzinfo=timezone.utc)
    # Current week begins September 7; the previous four begin August 10.
    a=replace(parcel('a',3000000),publication_label='2026-08-10T00:00:00Z')
    b=replace(parcel('b',None),publication_label='2026-09-06T23:59:59Z')
    c=replace(parcel('c',9000000),publication_label='2026-09-07T00:00:00Z')
    weeks=summarize_market([a,b,c],now=now)['semaines']
    assert len(weeks)==4 and weeks[0]['debut']=='2026-08-10' and weeks[-1]['fin']=='2026-09-06'
    assert [w['types']['parcelle']['annonces'] for w in weeks]==[1,0,0,1]
    assert weeks[0]['types']['parcelle']['prix_m2']==10000
    assert weeks[-1]['types']['parcelle']['prix_m2'] is None
    assert weeks[0]['types']['maison']['prix_m2'] is None
