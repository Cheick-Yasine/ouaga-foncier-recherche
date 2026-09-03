"""Tests de l'authentification et de la présentation des contacts."""

from app.auth import (
    AuthenticationError,
    AuthenticatedUser,
    hash_password,
    normalize_email,
    verify_password,
)
from app.contacts import mask_contact, whatsapp_url


def test_password_is_hashed_and_verified() -> None:
    encoded = hash_password("mot-de-passe-solide")

    assert "mot-de-passe-solide" not in encoded
    assert verify_password("mot-de-passe-solide", encoded) is True
    assert verify_password("mauvais-mot-de-passe", encoded) is False


def test_email_is_normalized() -> None:
    assert normalize_email("  Client@Example.COM ") == "client@example.com"


def test_invalid_email_is_rejected() -> None:
    try:
        normalize_email("adresse-invalide")
    except AuthenticationError:
        pass
    else:
        raise AssertionError("Une adresse invalide devait être refusée.")


def test_contact_is_masked_and_whatsapp_link_is_normalized() -> None:
    assert mask_contact("70 12 34 56") == "70 ** ** 56"
    assert whatsapp_url("70 12 34 56") == "https://wa.me/22670123456"
    assert whatsapp_url("+226 70 12 34 56") == "https://wa.me/22670123456"


def test_authenticated_user_is_immutable() -> None:
    user = AuthenticatedUser(id="user-1", email="client@example.com")
    assert user.email == "client@example.com"
