"""Configuration centralisée et sécurisée de l'application."""

from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Paramètres chargés depuis l'environnement ou le fichier local .env."""

    app_name: str = "Ouaga Foncier Recherche"
    app_env: str = "development"
    database_url: SecretStr | None = None
    max_ad_age_days: int = Field(default=7, ge=1, le=30)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return value

        url = value.get_secret_value()
        if not url.startswith(("postgresql://", "postgres://")):
            raise ValueError(
                "DATABASE_URL doit commencer par postgresql:// ou postgres://"
            )
        return value


@lru_cache
def get_settings() -> Settings:
    """Retourne une configuration unique pour le processus courant."""

    return Settings()
