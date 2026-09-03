"""Authentification par mot de passe et sessions opaques stockées dans Neon."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import psycopg
from psycopg.rows import dict_row

from app.config import get_settings
from app.database import DatabaseNotConfiguredError


SESSION_COOKIE = "of_session"
SESSION_DURATION = timedelta(days=30)
_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1


class AuthenticationError(ValueError):
    """Erreur d'inscription ou de connexion présentable au client."""


@dataclass(frozen=True)
class AuthenticatedUser:
    id: str
    email: str


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if len(normalized) > 254 or not _EMAIL_PATTERN.fullmatch(normalized):
        raise AuthenticationError("Adresse e-mail invalide.")
    return normalized


def validate_password(password: str) -> None:
    if len(password) < 10:
        raise AuthenticationError(
            "Le mot de passe doit contenir au moins 10 caractères."
        )
    if len(password) > 128:
        raise AuthenticationError("Le mot de passe est trop long.")


def hash_password(password: str) -> str:
    validate_password(password)
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=32,
    )
    return (
        f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}$"
        f"{salt.hex()}${digest.hex()}"
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt_hex, digest_hex = encoded.split("$")
        if algorithm != "scrypt":
            return False
        expected = bytes.fromhex(digest_hex)
        observed = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(observed, expected)


def _database_url() -> str:
    settings = get_settings()
    if settings.database_url is None:
        raise DatabaseNotConfiguredError(
            "DATABASE_URL n'est pas configurée dans l'environnement."
        )
    return settings.database_url.get_secret_value()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_user(email: str, password: str) -> AuthenticatedUser:
    normalized = normalize_email(email)
    password_hash = hash_password(password)
    user_id = str(uuid.uuid4())

    try:
        with psycopg.connect(_database_url(), connect_timeout=10) as connection:
            connection.execute(
                """
                INSERT INTO public.app_users (id, email, password_hash)
                VALUES (%s, %s, %s)
                """,
                (user_id, normalized, password_hash),
            )
    except psycopg.errors.UniqueViolation as error:
        raise AuthenticationError(
            "Un compte existe déjà avec cette adresse e-mail."
        ) from error

    return AuthenticatedUser(id=user_id, email=normalized)


def authenticate_user(email: str, password: str) -> AuthenticatedUser | None:
    normalized = normalize_email(email)
    with psycopg.connect(
        _database_url(),
        connect_timeout=10,
        row_factory=dict_row,
    ) as connection:
        row = connection.execute(
            """
            SELECT id::text AS id, email, password_hash
            FROM public.app_users
            WHERE email = %s
            """,
            (normalized,),
        ).fetchone()

    if row is None or not verify_password(password, row["password_hash"]):
        return None
    return AuthenticatedUser(id=row["id"], email=row["email"])


def create_session(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + SESSION_DURATION
    with psycopg.connect(_database_url(), connect_timeout=10) as connection:
        connection.execute(
            """
            INSERT INTO public.user_sessions (token_hash, user_id, expires_at)
            VALUES (%s, %s, %s)
            """,
            (_token_hash(token), user_id, expires_at),
        )
    return token


def get_session_user(token: str | None) -> AuthenticatedUser | None:
    if not token:
        return None
    with psycopg.connect(
        _database_url(),
        connect_timeout=10,
        row_factory=dict_row,
    ) as connection:
        row = connection.execute(
            """
            SELECT users.id::text AS id, users.email
            FROM public.user_sessions AS sessions
            JOIN public.app_users AS users ON users.id = sessions.user_id
            WHERE sessions.token_hash = %s
              AND sessions.expires_at > CURRENT_TIMESTAMP
            """,
            (_token_hash(token),),
        ).fetchone()

    if row is None:
        return None
    return AuthenticatedUser(id=row["id"], email=row["email"])


def delete_session(token: str | None) -> None:
    if not token:
        return
    with psycopg.connect(_database_url(), connect_timeout=10) as connection:
        connection.execute(
            "DELETE FROM public.user_sessions WHERE token_hash = %s",
            (_token_hash(token),),
        )
