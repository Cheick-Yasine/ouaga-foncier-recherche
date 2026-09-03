"""Présentation sûre des contacts issus des annonces."""

import re


def mask_contact(contact: str | None) -> str | None:
    if not contact:
        return None
    digits = re.sub(r"\D", "", contact)
    if len(digits) < 4:
        return "Contact disponible"
    return f"{digits[:2]} ** ** {digits[-2:]}"


def whatsapp_url(contact: str | None) -> str | None:
    if not contact:
        return None
    first = re.split(r"[;,/]|\bou\b", contact, maxsplit=1)[0]
    digits = re.sub(r"\D", "", first)
    if len(digits) == 8:
        digits = "226" + digits
    if len(digits) < 8 or len(digits) > 15:
        return None
    return f"https://wa.me/{digits}"
