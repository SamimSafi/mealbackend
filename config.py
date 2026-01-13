"""Application configuration."""
import os
from pathlib import Path
from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    # Server
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000

    # Database - supports both SQLite (local) and MySQL (production)
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "local")
    
    # MySQL settings (for production/PythonAnywhere)
    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "samimsafi.mysql.pythonanywhere-services.com")
    MYSQL_USER: str = os.getenv("MYSQL_USER", "samimsafi")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "Meal@123")
    MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "samimsafi$kobo_dashboard")
    
    # SQLite settings (for local development)
    SQLITE_PATH: str = os.getenv("SQLITE_PATH", "kobo_dashboard.db")
    
    @computed_field  # type: ignore[misc]
    @property
    def DATABASE_URL(self) -> str:
        """Get database URL based on environment."""
        if self.ENVIRONMENT.lower() == "production":
            # MySQL for production/PythonAnywhere
            url = f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}/{self.MYSQL_DATABASE}"
            return url
        else:
            # SQLite for local development
            db_path = Path(self.SQLITE_PATH)
            if not db_path.is_absolute():
                db_path = Path(__file__).parent / db_path
            
            db_path.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite:///{str(db_path)}"

    # JWT
    SECRET_KEY: str = "4b9e5d9db5c14a5a8d0e4ea2c2f4d9f0e6d8a7c3c5f1a9b2c4d6e8f0a1b3c5d7e9f2a4b6c8d0e2f4a6c8e0f1a3b5c7d9e1f3a5c7e9f1d3c5b7a9"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # KoboToolbox
    KOBO_API_URL: str = "https://kf.kobotoolbox.org/api/v2"
    KOBO_API_TOKEN: str = "6a5572c598cfb893a5db16a98494660009fbc648"
    KOBO_USERNAME: str = ""

       # CORS - stored as comma-separated string in .env, converted to list
    CORS_ORIGINS_STR: str = "http://localhost:5173,http://localhost:3000,http://samimsafi22-001-site1.jtempurl.com,https://samimsafi22-001-site1.jtempurl.com"


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

