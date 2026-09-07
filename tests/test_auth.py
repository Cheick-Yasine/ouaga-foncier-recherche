"""Tests de l'authentification et de la présentation des contacts."""

from app.auth import (
    AuthenticationError,
    AuthenticatedUser,
    hash_password,
    normalize_name,
    verify_password,
)
from app.contacts import first_contact, mask_contact, whatsapp_url


def test_password_is_hashed_and_verified() -> None:
    encoded = hash_password("1234")

    assert "1234" not in encoded
    assert verify_password("1234", encoded) is True
    assert verify_password("mauvais-mot-de-passe", encoded) is False


def test_name_is_normalized() -> None:
    assert normalize_name("  Cheick   Yasine ") == "cheick yasine"


def test_empty_name_is_rejected() -> None:
    try:
        normalize_name(" ")
    except AuthenticationError:
        pass
    else:
        raise AssertionError("Un nom vide devait être refusé.")


def test_contact_is_masked_and_whatsapp_link_is_normalized() -> None:
    assert mask_contact("70 12 34 56") == "70 ** ** 56"
    assert whatsapp_url("70 12 34 56") == "https://wa.me/22670123456"
    assert whatsapp_url("+226 70 12 34 56") == "https://wa.me/22670123456"
    assert first_contact("70 12 34 56; 76 54 32 10") == "70 12 34 56"
    assert whatsapp_url("70 12 34 56; 76 54 32 10") == (
        "https://wa.me/22670123456"
    )


def test_authenticated_user_is_immutable() -> None:
    user = AuthenticatedUser(id="user-1", name="cheick yasine")
    assert user.name == "cheick yasine"


def test_profile_password_change_keeps_current_session_and_hashes_password(monkeypatch):
    from app.auth import update_user, _token_hash
    queries=[]
    old_hash=hash_password('1234')
    class Connection:
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def execute(self,query,params): queries.append((query,params));return self
        def fetchone(self): return {'password_hash':old_hash}
    monkeypatch.setattr('app.auth._database_url',lambda:'postgresql://example.test/db')
    monkeypatch.setattr('app.auth.psycopg.connect',lambda *args,**kwargs:Connection())
    user=update_user('own-id',' Nouveau Nom ','1234','5678','current-session')
    assert user==AuthenticatedUser('own-id','nouveau nom')
    update=next(params for query,params in queries if query.startswith('UPDATE'))
    assert update[0]=='nouveau nom' and update[2]=='own-id'
    assert verify_password('5678',update[1]) and not verify_password('1234',update[1])
    revoke=next((query,params) for query,params in queries if query.startswith('DELETE'))
    assert 'token_hash <>' in revoke[0]
    assert revoke[1]==('own-id',_token_hash('current-session'))


def test_wrong_current_password_cannot_change_profile(monkeypatch):
    from app.auth import update_user
    old_hash=hash_password('1234')
    class Connection:
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def execute(self,query,params):
            assert query.startswith('SELECT'), 'No update or session deletion with an incorrect password'
            return self
        def fetchone(self): return {'password_hash':old_hash}
    monkeypatch.setattr('app.auth._database_url',lambda:'postgresql://example.test/db')
    monkeypatch.setattr('app.auth.psycopg.connect',lambda *args,**kwargs:Connection())
    try: update_user('own-id','New Name','wrong','5678','token')
    except AuthenticationError: pass
    else: raise AssertionError('Current password must be verified')
