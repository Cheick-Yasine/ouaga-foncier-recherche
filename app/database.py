"""Accès minimal à PostgreSQL/Neon."""

import psycopg

from app.config import Settings, get_settings


class DatabaseNotConfiguredError(RuntimeError):
    """La variable DATABASE_URL n'est pas disponible."""


def check_database_connection(settings: Settings | None = None) -> bool:
    """Exécute SELECT 1 sans exposer l'adresse ni les identifiants de Neon."""

    current_settings = settings or get_settings()
    if current_settings.database_url is None:
        raise DatabaseNotConfiguredError(
            "DATABASE_URL n'est pas configurée dans l'environnement."
        )

    database_url = current_settings.database_url.get_secret_value()
    with psycopg.connect(database_url, connect_timeout=10) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()

    return bool(result and result[0] == 1)
