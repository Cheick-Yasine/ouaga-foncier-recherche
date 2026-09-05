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
