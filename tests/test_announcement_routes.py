"""Tests de la consultation protégée des annonces."""

from fastapi.testclient import TestClient

from app.auth import AuthenticatedUser
from app.main import app
from app.public_references import public_announcement_id
from app.search_engine import SearchCandidate


client = TestClient(app)


def test_announcement_requires_authentication(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.announcement_routes.get_session_user",
        lambda _token: None,
    )

    response = client.get("/annonces/reference")
    assert response.status_code == 401
    assert response.json()["detail"] == "Connexion requise."


def test_authenticated_user_can_view_contact_and_source(monkeypatch) -> None:
    candidate = SearchCandidate(
        identifier="post-secret",
        text="Parcelle à Saaba de 300 m2",
        property_type="parcelle",
        neighborhood="Saaba",
        price_fcfa=4_000_000,
        area_m2=300,
        document_status="attestation",
        url="https://facebook.com/posts/secret",
        contact="70 12 34 56; 76 54 32 10",
    )
    monkeypatch.setattr(
        "app.announcement_routes.get_session_user",
        lambda _token: AuthenticatedUser(id="user-1", name="cheick yasine"),
    )
    monkeypatch.setattr(
        "app.announcement_routes.load_recent_candidates",
        lambda _days: [candidate],
    )

    reference = public_announcement_id(candidate.identifier)
    response = client.get(
        f"/annonces/{reference}",
        cookies={"of_session": "token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == reference
    assert payload["contact"] == "70 12 34 56"
    assert payload["lien_whatsapp"] == "https://wa.me/22670123456"
    assert payload["url"] == "https://facebook.com/posts/secret"
    assert "post-secret" not in response.text


def test_contacts_load_together_without_exposing_unselected_ads(monkeypatch):
    monkeypatch.setattr('app.announcement_routes.get_session_user',lambda _:AuthenticatedUser(id='u',name='Utilisateur'))
    candidates=[SearchCandidate(identifier='a',text='Parcelle',contact='70 12 34 56; 76 54 32 10'),SearchCandidate(identifier='b',text='Autre annonce',contact='77 88 99 00')]
    calls=[]
    def load(refs, *, include_contacts):
        calls.append((refs, include_contacts))
        return [{'id': c.identifier, 'contacts_whatsapp': c.contact} for c in candidates if public_announcement_id(c.identifier) in refs]
    monkeypatch.setattr('app.announcement_routes.read_references',load)
    ref=public_announcement_id('a')
    response=client.post('/annonces/selection',json={'references':[ref]})
    assert response.status_code==200
    assert calls==[([ref], True)]
    assert response.json()==[{'id':ref,'contact':'70 12 34 56','lien_whatsapp':'https://wa.me/22670123456'}]
    assert '77 88 99 00' not in response.text


def test_contacts_and_facebook_source_require_login(monkeypatch):
    monkeypatch.setattr('app.announcement_routes.get_session_user',lambda _:None)
    def forbidden(_):
        raise AssertionError('No database read before authentication')
    monkeypatch.setattr('app.announcement_routes.load_recent_candidates',forbidden)
    assert client.post('/annonces/selection',json={'references':['a']}).status_code==401
    assert client.get('/annonces/a/source',follow_redirects=False).status_code==401


def test_view_opens_original_facebook_publication(monkeypatch):
    monkeypatch.setattr('app.announcement_routes.get_session_user',lambda _:AuthenticatedUser(id='u',name='Utilisateur'))
    monkeypatch.setattr('app.announcement_routes.load_recent_candidates',lambda _:[SearchCandidate(identifier='a',text='Parcelle',url='https://www.facebook.com/groups/123/posts/456/')])
    response=client.get('/annonces/'+public_announcement_id('a')+'/source',follow_redirects=False)
    assert response.status_code==303
    assert response.headers['location']=='https://www.facebook.com/groups/123/posts/456/'


def test_source_does_not_redirect_to_non_facebook_host(monkeypatch):
    monkeypatch.setattr('app.announcement_routes.get_session_user',lambda _:AuthenticatedUser(id='u',name='Utilisateur'))
    for url in ['javascript:alert(1)', 'https://facebook.com.evil.test/post', 'https://facebook.com@evil.test/post']:
        monkeypatch.setattr('app.announcement_routes.load_recent_candidates',lambda _,url=url:[SearchCandidate(identifier='a',text='Parcelle',url=url)])
        assert client.get('/annonces/a/source',follow_redirects=False).status_code==404
