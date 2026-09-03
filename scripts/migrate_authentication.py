"""Applique les migrations applicatives idempotentes sur Neon."""

from pathlib import Path

import psycopg

from app.config import get_settings
from app.database import DatabaseNotConfiguredError


def apply_authentication_migration() -> None:
    settings = get_settings()
    if settings.database_url is None:
        raise DatabaseNotConfiguredError(
            "DATABASE_URL n'est pas configurée dans l'environnement."
        )

    migration = (
        Path(__file__).resolve().parents[1]
        / "db"
        / "migrations"
        / "001_authentication.sql"
    ).read_text(encoding="utf-8")

    with psycopg.connect(
        settings.database_url.get_secret_value(),
        connect_timeout=10,
    ) as connection:
        with connection.transaction():
            connection.execute(migration)


def main() -> int:
    apply_authentication_migration()
    print("Migration authentification appliquée avec succès.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
