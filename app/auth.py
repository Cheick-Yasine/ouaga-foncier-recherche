"""Authentification par mot de passe et sessions opaques stockées dans Neon."""

from __future__ import annotations

import hashlib
import hmac
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
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1


class AuthenticationError(ValueError):
    """Erreur d'inscription ou de connexion présentable au client."""


@dataclass(frozen=True)
class AuthenticatedUser:
    id: str
    name: str


def normalize_name(name: str) -> str:
    normalized = " ".join(name.strip().split()).lower()
    if not 2 <= len(normalized) <= 80:
        raise AuthenticationError("Le nom doit contenir entre 2 et 80 caractères.")
    if any(ord(character) < 32 for character in normalized):
        raise AuthenticationError("Nom invalide.")
    return normalized


def validate_password(password: str) -> None:
    if len(password) < 4:
        raise AuthenticationError(
            "Le mot de passe doit contenir au moins 4 caractères."
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


def create_user(name: str, password: str) -> AuthenticatedUser:
    normalized = normalize_name(name)
    password_hash = hash_password(password)
    user_id = str(uuid.uuid4())

    try:
        with psycopg.connect(_database_url()) as connection:
            connection.execute(
                """
                INSERT INTO public.app_users (id, email, password_hash)
                VALUES (%s, %s, %s)
                """,
                (user_id, normalized, password_hash),
            )
    except psycopg.errors.UniqueViolation as error:
        raise AuthenticationError(
            "Un compte existe déjà avec ce nom."
        ) from error

    return AuthenticatedUser(id=user_id, name=normalized)


def authenticate_user(name: str, password: str) -> AuthenticatedUser | None:
    normalized = normalize_name(name)
    with psycopg.connect(
        _database_url(),
        row_factory=dict_row,
    ) as connection:
        row = connection.execute(
            """
            SELECT id::text AS id, email AS name, password_hash
            FROM public.app_users
            WHERE email = %s
            """,
            (normalized,),
        ).fetchone()

    if row is None or not verify_password(password, row["password_hash"]):
        return None
    return AuthenticatedUser(id=row["id"], name=row["name"])


def create_session(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + SESSION_DURATION
    with psycopg.connect(_database_url()) as connection:
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
        row_factory=dict_row,
    ) as connection:
        row = connection.execute(
            """
            SELECT users.id::text AS id, users.email AS name
            FROM public.user_sessions AS sessions
            JOIN public.app_users AS users ON users.id = sessions.user_id
            WHERE sessions.token_hash = %s
              AND sessions.expires_at > CURRENT_TIMESTAMP
            """,
            (_token_hash(token),),
        ).fetchone()

    if row is None:
        return None
    return AuthenticatedUser(id=row["id"], name=row["name"])


def delete_session(token: str | None) -> None:
    if not token:
        return
    with psycopg.connect(_database_url()) as connection:
        connection.execute(
            "DELETE FROM public.user_sessions WHERE token_hash = %s",
            (_token_hash(token),),
        )


def update_user(user_id: str, name: str, current_password: str,
                new_password: str | None, session_token: str) -> AuthenticatedUser:
    """Modifie le compte connecté, en conservant son identifiant et ses favoris."""
    normalized = normalize_name(name)
    validate_password(current_password)
    if new_password is not None:
        validate_password(new_password)
    try:
        with psycopg.connect(_database_url(), row_factory=dict_row) as connection:
            row = connection.execute(
                'SELECT password_hash FROM public.app_users WHERE id = %s FOR UPDATE',
                (user_id,),
            ).fetchone()
            if row is None or not verify_password(current_password, row['password_hash']):
                raise AuthenticationError('Le mot de passe actuel est incorrect.')
            password_hash = hash_password(new_password) if new_password is not None else row['password_hash']
            connection.execute(
                'UPDATE public.app_users SET email = %s, password_hash = %s WHERE id = %s',
                (normalized, password_hash, user_id),
            )
            if new_password is not None:
                connection.execute(
                    'DELETE FROM public.user_sessions WHERE user_id = %s AND token_hash <> %s',
                    (user_id, _token_hash(session_token)),
                )
    except psycopg.errors.UniqueViolation as error:
        raise AuthenticationError('Un compte existe déjà avec ce nom.') from error
    return AuthenticatedUser(id=user_id, name=normalized)
