"""Configuration centralisée et sécurisée de l'application."""

from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Paramètres chargés depuis l'environnement ou le fichier local .env."""

    app_name: str = "Ouaga Foncier Recherche"
    app_env: str = "development"
    public_app_url: str = "https://ouaga-foncier-mcp.onrender.com"
    database_url: SecretStr | None = None
    max_ad_age_days: int | None = Field(default=None, ge=1, le=365)
    openai_api_key: SecretStr | None = None
    llm_model: str = "gpt-4o-mini"
    llm_candidate_limit: int = Field(default=15, ge=10, le=30)
    llm_relevance_threshold: int = Field(default=55, ge=0, le=100)
    llm_deadline_seconds: float = Field(default=25.0, ge=0.05, le=60.0)
    database_deadline_seconds: float = Field(default=15.0, ge=0.05, le=30.0)

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

    @field_validator("public_app_url")
    @classmethod
    def validate_public_app_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if not normalized.startswith(("https://", "http://localhost", "http://127.0.0.1")):
            raise ValueError("PUBLIC_APP_URL doit être une URL HTTPS publique.")
        return normalized


@lru_cache
def get_settings() -> Settings:
    """Retourne une configuration unique pour le processus courant."""

    return Settings()
