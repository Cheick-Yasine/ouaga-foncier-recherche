"""Routes de recherche et interprétation des demandes."""

from __future__ import annotations

from dataclasses import replace
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.search_engine import SearchCriteria, parse_search_description


RequiredField = Literal[
    "quartier",
    "prix",
    "superficie",
    "type_bien",
    "statut_document",
    "proximite",
    "viabilite",
]


class InterpretRequest(BaseModel):
    description: str = Field(min_length=3, max_length=2_000)
    required_fields: set[RequiredField] = Field(default_factory=set)
    max_age_days: int = Field(default=7, ge=1, le=31)


class InterpretedCriteria(BaseModel):
    description: str
    type_bien: str | None
    quartier: str | None
    prix_fcfa: float | None
    prix_est_un_maximum: bool
    superficie_m2: float | None
    proximite: str | None
    viabilite: str | None
    statut_document: str | None
    contraintes_obligatoires: list[str]
    anciennete_maximale_jours: int


router = APIRouter(prefix="/search", tags=["Recherche"])


def _response(criteria: SearchCriteria) -> InterpretedCriteria:
    return InterpretedCriteria(
        description=criteria.description,
        type_bien=criteria.property_type,
        quartier=criteria.neighborhood,
        prix_fcfa=criteria.price_fcfa,
        prix_est_un_maximum=criteria.price_is_maximum,
        superficie_m2=criteria.area_m2,
        proximite=criteria.proximity,
        viabilite=criteria.viability,
        statut_document=criteria.document_status,
        contraintes_obligatoires=sorted(criteria.required_fields),
        anciennete_maximale_jours=criteria.max_age_days,
    )


@router.post("/interpret", response_model=InterpretedCriteria)
def interpret_search(payload: InterpretRequest) -> InterpretedCriteria:
    criteria = parse_search_description(payload.description)
    criteria = replace(
        criteria,
        required_fields=frozenset(payload.required_fields),
        max_age_days=payload.max_age_days,
    )
    return _response(criteria)
