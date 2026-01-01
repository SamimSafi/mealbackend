"""Application configuration."""
from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    # Server
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000

    # Database
    DATABASE_URL: str = "sqlite:///./data/kobo_dashboard.db"

    # JWT
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # KoboToolbox
    KOBO_API_URL: str = "https://kf.kobotoolbox.org/api/v2"
    KOBO_API_TOKEN: str = ""
    KOBO_USERNAME: str = ""

    # CORS - stored as comma-separated string in .env, converted to list
    CORS_ORIGINS_STR: str = "http://localhost:5173,http://localhost:3000"

    # Webhook
    WEBHOOK_SECRET: str = ""

    @computed_field  # type: ignore[misc]
    @property
    def CORS_ORIGINS(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.CORS_ORIGINS_STR.split(",") if origin.strip()]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        env_ignore_empty=True,
        extra="ignore"
    )


settings = Settings()

