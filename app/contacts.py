"""Présentation sûre des contacts issus des annonces."""

import re


def first_contact(contact: str | None) -> str | None:
    if not contact:
        return None
    first = re.split(
        r"[;,/|\n]|\bou\b",
        contact,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    digits = re.sub(r"\D", "", first)
    if len(digits) == 11 and digits.startswith("226"):
        local = digits[-8:]
        return "+226 " + " ".join(
            local[index:index + 2] for index in range(0, 8, 2)
        )
    if len(digits) == 8:
        return " ".join(
            digits[index:index + 2] for index in range(0, 8, 2)
        )
    return first.strip() or None


def mask_contact(contact: str | None) -> str | None:
    visible = first_contact(contact)
    if not visible:
        return None
    digits = re.sub(r"\D", "", visible)
    if len(digits) == 11 and digits.startswith("226"):
        digits = digits[-8:]
    if len(digits) < 4:
        return "Contact disponible"
    return f"{digits[:2]} ** ** {digits[-2:]}"


def whatsapp_url(contact: str | None) -> str | None:
    visible = first_contact(contact)
    if not visible:
        return None
    digits = re.sub(r"\D", "", visible)
    if len(digits) == 8:
        digits = "226" + digits
    if len(digits) < 8 or len(digits) > 15:
        return None
    return f"https://wa.me/{digits}"
