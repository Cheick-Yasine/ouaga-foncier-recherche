"""Accueil public, liens Facebook et modification du seul compte connecté."""
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.auth import AuthenticatedUser, AuthenticationError, SESSION_COOKIE
from app.database import DatabaseNotConfiguredError
from app.main import app
from app.public_references import public_announcement_id
from app.search_engine import SearchCandidate

client = TestClient(app)


def test_stats_are_public_aggregates_without_search_pool_limit(monkeypatch):
    candidate=SearchCandidate('a','Parcelle en vente à Karpala', neighborhood='Karpala', price_fcfa=3_000_000, area_m2=300, publication_label=datetime.now(timezone.utc).isoformat(), contact='70 12 34 56')
    calls=[]
    def load(days, *, pool_limit):
        calls.append((days,pool_limit)); return [candidate]
    monkeypatch.setattr('app.market_routes.load_recent_candidates',load)
    response=client.get('/market/stats')
    assert response.status_code==200
    assert calls==[(None,None)]
    assert response.json()['annonces_30_jours']==1
    assert response.json()['prix_m2_moyen_fcfa']==10_000
    assert '70 12 34 56' not in response.text
    assert 'contact' not in response.text


def test_stats_unavailable_is_not_reported_as_zero(monkeypatch):
    def failed(*args,**kwargs): raise DatabaseNotConfiguredError('No database')
    monkeypatch.setattr('app.market_routes.load_recent_candidates',failed)
    response=client.get('/market/stats')
    assert response.status_code==503
    assert 'annonces_30_jours' not in response.json()


def test_legacy_favorites_resolve_public_sources_without_contact_or_redirect(monkeypatch):
    source='https://www.facebook.com/groups/123/posts/456/'
    candidates=[SearchCandidate('a','Annonce privée du contact',url=source,contact='70 12 34 56'), SearchCandidate('b','Autre',url='https://facebook.com/posts/other')]
    monkeypatch.setattr('app.announcement_routes.load_recent_candidates',lambda *a,**k:candidates)
    ref=public_announcement_id('a')
    response=client.post('/annonces/liens',json={'references':[ref]})
    assert response.status_code==200
    assert response.json()==[{'id':ref,'facebook_url':source}]
    assert 'location' not in response.headers
    assert 'contact' not in response.text
    assert '70 12 34 56' not in response.text
    assert 'other' not in response.text


def test_profile_update_requires_a_session_before_mutation(monkeypatch):
    monkeypatch.setattr('app.auth_routes.get_session_user',lambda _:None)
    def forbidden(*args): raise AssertionError('No mutation for anonymous user')
    monkeypatch.setattr('app.auth_routes.update_user',forbidden)
    response=client.patch('/auth/me',json={'name':'nouveau nom','current_password':'1234'})
    assert response.status_code==401


def test_profile_keeps_identity_and_uses_authenticated_account(monkeypatch):
    monkeypatch.setattr('app.auth_routes.get_session_user',lambda _:AuthenticatedUser('own-id','ancien nom'))
    calls=[]
    def update(user_id,name,password,new_password,token):
        calls.append((user_id,name,password,new_password,token));return AuthenticatedUser(user_id,name)
    monkeypatch.setattr('app.auth_routes.update_user',update)
    response=client.patch('/auth/me',json={'id':'another-user','name':'nouveau nom','current_password':'1234','new_password':'5678'},cookies={SESSION_COOKIE:'session-token'})
    assert response.status_code==200
    assert response.json()=={'id':'own-id','name':'nouveau nom'}
    assert calls==[('own-id','nouveau nom','1234','5678','session-token')]
    assert 'password' not in response.text


def test_profile_rejects_wrong_password(monkeypatch):
    monkeypatch.setattr('app.auth_routes.get_session_user',lambda _:AuthenticatedUser('own-id','nom'))
    def reject(*args): raise AuthenticationError('Le mot de passe actuel est incorrect.')
    monkeypatch.setattr('app.auth_routes.update_user',reject)
    response=client.patch('/auth/me',json={'name':'nouveau nom','current_password':'wrong'},cookies={SESSION_COOKIE:'session-token'})
    assert response.status_code==400
    assert 'actuel' in response.json()['detail']


def test_profile_requires_current_password_and_valid_new_password(monkeypatch):
    def forbidden(*args): raise AssertionError('Invalid form must not reach database')
    monkeypatch.setattr('app.auth_routes.update_user',forbidden)
    assert client.patch('/auth/me',json={'name':'nom'}).status_code==422
    assert client.patch('/auth/me',json={'name':'nom','current_password':'1234','new_password':'x'}).status_code==422
