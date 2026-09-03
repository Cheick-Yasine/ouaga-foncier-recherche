"""Routes de création de compte, connexion et session."""

import psycopg
from fastapi import APIRouter, Cookie, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.auth import (
    SESSION_COOKIE,
    SESSION_DURATION,
    AuthenticationError,
    AuthenticatedUser,
    authenticate_user,
    create_session,
    create_user,
    delete_session,
    get_session_user,
)
from app.config import get_settings
from app.database import DatabaseNotConfiguredError


class Credentials(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=10, max_length=128)


class UserResponse(BaseModel):
    id: str
    email: str


router = APIRouter(prefix="/auth", tags=["Authentification"])


def _user_response(user: AuthenticatedUser) -> UserResponse:
    return UserResponse(id=user.id, email=user.email)


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=int(SESSION_DURATION.total_seconds()),
        httponly=True,
        secure=settings.app_env != "development",
        samesite="lax",
        path="/",
    )


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(payload: Credentials, response: Response) -> UserResponse:
    try:
        user = create_user(payload.email, payload.password)
        token = create_session(user.id)
    except AuthenticationError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    except (DatabaseNotConfiguredError, psycopg.Error):
        raise HTTPException(
            status_code=503,
            detail="Le service de connexion est temporairement indisponible.",
        ) from None

    _set_session_cookie(response, token)
    return _user_response(user)


@router.post("/login", response_model=UserResponse)
def login(payload: Credentials, response: Response) -> UserResponse:
    try:
        user = authenticate_user(payload.email, payload.password)
        if user is None:
            raise HTTPException(
                status_code=401,
                detail="Adresse e-mail ou mot de passe incorrect.",
            )
        token = create_session(user.id)
    except AuthenticationError:
        raise HTTPException(
            status_code=401,
            detail="Adresse e-mail ou mot de passe incorrect.",
        ) from None
    except (DatabaseNotConfiguredError, psycopg.Error):
        raise HTTPException(
            status_code=503,
            detail="Le service de connexion est temporairement indisponible.",
        ) from None

    _set_session_cookie(response, token)
    return _user_response(user)


@router.get("/me", response_model=UserResponse)
def me(
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> UserResponse:
    try:
        user = get_session_user(session_token)
    except (DatabaseNotConfiguredError, psycopg.Error):
        raise HTTPException(
            status_code=503,
            detail="Le service de connexion est temporairement indisponible.",
        ) from None
    if user is None:
        raise HTTPException(status_code=401, detail="Connexion requise.")
    return _user_response(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> None:
    try:
        delete_session(session_token)
    except (DatabaseNotConfiguredError, psycopg.Error):
        pass
    response.delete_cookie(SESSION_COOKIE, path="/")
