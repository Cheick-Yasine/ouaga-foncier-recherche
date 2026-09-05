"""Consultation protégée d'une annonce depuis une référence publique."""

import psycopg
from urllib.parse import urlsplit
from fastapi import APIRouter, Cookie, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.auth import SESSION_COOKIE, get_session_user
from app.contacts import first_contact, whatsapp_url
from app.database import DatabaseNotConfiguredError
from app.public_references import public_announcement_id
from app.search_repository import load_recent_candidates


class AnnouncementDetail(BaseModel):
    id: str
    texte: str
    url: str | None
    date_publication: str | None
    type_bien: str | None
    quartier: str | None
    prix_fcfa: float | None
    superficie_m2: float | None
    statut_document: str | None
    contact: str | None
    lien_whatsapp: str | None


router = APIRouter(prefix="/annonces", tags=["Annonces"])


class AnnouncementSelection(BaseModel):
    references: list[str] = Field(min_length=1, max_length=500)


class AnnouncementContact(BaseModel):
    id: str
    contact: str | None
    lien_whatsapp: str | None


@router.post("/selection", response_model=list[AnnouncementContact])
def announcement_contacts(
    selection: AnnouncementSelection,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> list[AnnouncementContact]:
    """Charge les contacts du tableau en une seule lecture, après connexion."""
    try:
        if get_session_user(session_token) is None:
            raise HTTPException(status_code=401, detail="Connexion requise.")
        candidates = load_recent_candidates(None)
    except (DatabaseNotConfiguredError, psycopg.Error):
        raise HTTPException(status_code=503, detail="Contacts temporairement indisponibles.") from None
    requested = set(selection.references)
    contacts = []
    for candidate in candidates:
        for reference in {public_announcement_id(candidate.identifier), candidate.identifier} & requested:
            contact = first_contact(candidate.contact)
            contacts.append(AnnouncementContact(id=reference, contact=contact, lien_whatsapp=whatsapp_url(contact)))
    return contacts


@router.get("/{reference}/source")
def announcement_source(
    reference: str,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> RedirectResponse:
    """Le lien Voir mène directement à la publication Facebook d'origine."""
    detail = announcement_detail(reference, session_token)
    try:
        url = urlsplit(detail.url or "")
        host = (url.hostname or "").lower()
        valid = url.scheme in {"http", "https"} and not url.username and not url.password
        valid = valid and any(host == domain or host.endswith("." + domain) for domain in ("facebook.com", "fb.com", "fb.watch"))
    except ValueError:
        valid = False
    if not valid:
        raise HTTPException(status_code=404, detail="Lien Facebook indisponible pour cette annonce.")
    return RedirectResponse(detail.url, status_code=303, headers={"Cache-Control": "no-store"})


@router.get("/{reference}", response_model=AnnouncementDetail)
def announcement_detail(
    reference: str,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> AnnouncementDetail:
    """Révèle le contact et le lien source uniquement à un utilisateur connecté."""

    try:
        if get_session_user(session_token) is None:
            raise HTTPException(status_code=401, detail="Connexion requise.")
        candidates = load_recent_candidates(None)
    except HTTPException:
        raise
    except (DatabaseNotConfiguredError, psycopg.Error):
        raise HTTPException(
            status_code=503,
            detail="L'annonce est temporairement indisponible.",
        ) from None

    candidate = next(
        (
            item
            for item in candidates
            if public_announcement_id(item.identifier) == reference
            or item.identifier == reference  # anciens enregistrements, après connexion
        ),
        None,
    )
    if candidate is None:
        raise HTTPException(status_code=404, detail="Annonce introuvable.")

    contact = first_contact(candidate.contact)
    return AnnouncementDetail(
        id=reference,
        texte=candidate.text,
        url=candidate.url,
        date_publication=candidate.publication_label,
        type_bien=candidate.property_type,
        quartier=candidate.neighborhood,
        prix_fcfa=candidate.price_fcfa,
        superficie_m2=candidate.area_m2,
        statut_document=candidate.document_status,
        contact=contact,
        lien_whatsapp=whatsapp_url(contact),
    )
