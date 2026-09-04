"""Références publiques opaques, sans divulgation des identifiants Neon."""

import hashlib


def public_announcement_id(identifier: str) -> str:
    """Produit une référence stable non réversible pour une annonce."""

    return hashlib.blake2b(
        identifier.encode("utf-8"),
        digest_size=12,
        person=b"ouaga-mcp",
    ).hexdigest()
