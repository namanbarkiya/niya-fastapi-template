from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List


class Settings(BaseSettings):
    """Application settings — all values come from environment variables."""

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    # Full async DSN, e.g.:
    #   Local:  postgresql+asyncpg://postgres:pass@localhost:5432/mydb
    #   Cloud:  postgresql+asyncpg://user:pass@host:5432/db?ssl=require
    database_url: str = Field(..., env="DATABASE_URL")

    # ------------------------------------------------------------------
    # JWT / Auth
    # ------------------------------------------------------------------
    jwt_secret: str = Field(..., env="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")

    # Short-lived access token (minutes)
    access_token_expire_minutes: int = Field(default=15, env="ACCESS_TOKEN_EXPIRE_MINUTES")

    # Long-lived refresh token (days)
    refresh_token_expire_days: int = Field(default=30, env="REFRESH_TOKEN_EXPIRE_DAYS")

    # ------------------------------------------------------------------
    # Cookie settings
    # ------------------------------------------------------------------
    cookie_secure: bool = Field(default=True, env="COOKIE_SECURE")
    cookie_httponly: bool = Field(default=True, env="COOKIE_HTTPONLY")
    cookie_samesite: str = Field(default="lax", env="COOKIE_SAMESITE")

    # ------------------------------------------------------------------
    # Email (for verification / password-reset emails)
    # ------------------------------------------------------------------
    # Set these only if you wire up an email provider (SMTP / SendGrid / etc.)
    smtp_host: str = Field(default="", env="SMTP_HOST")
    smtp_port: int = Field(default=587, env="SMTP_PORT")
    smtp_user: str = Field(default="", env="SMTP_USER")
    smtp_password: str = Field(default="", env="SMTP_PASSWORD")
    email_from: str = Field(default="noreply@example.com", env="EMAIL_FROM")

    # Base URL for email confirmation / reset links sent to users
    app_base_url: str = Field(default="http://localhost:3000", env="APP_BASE_URL")

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------
    app_name: str = Field(default="Niya API", env="APP_NAME")
    debug: bool = Field(default=False, env="DEBUG")
    environment: str = Field(default="production", env="ENVIRONMENT")

    # ------------------------------------------------------------------
    # Rate Limiting
    # ------------------------------------------------------------------
    rate_limit_per_minute: int = Field(default=60, env="RATE_LIMIT_PER_MINUTE")

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    # ------------------------------------------------------------------
    # CORS
    # ------------------------------------------------------------------
    cors_origins: List[str] = Field(
        default=["http://localhost:3000"],
        env="CORS_ORIGINS",
    )

    model_config = {"env_file": ".env", "case_sensitive": False}


settings = Settings()


def get_settings() -> Settings:
    return settings
