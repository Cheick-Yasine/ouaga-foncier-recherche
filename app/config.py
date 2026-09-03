"""Configuration centralisée et sécurisée de l'application."""

from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Paramètres chargés depuis l'environnement ou le fichier local .env."""

    app_name: str = "Ouaga Foncier Recherche"
    app_env: str = "development"
    database_url: SecretStr | None = None
    max_ad_age_days: int | None = Field(default=None, ge=1, le=365)
    openai_api_key: SecretStr | None = None
    llm_model: str = "gpt-5.6-luna"
    llm_candidate_limit: int = Field(default=30, ge=5, le=50)
    llm_relevance_threshold: int = Field(default=55, ge=0, le=100)

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
