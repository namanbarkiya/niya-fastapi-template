"""
Application settings — all values come from environment variables via pydantic-settings.
"""
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings — all values come from environment variables."""

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    database_url: str

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_db_url(cls, v: str) -> str:
        """
        Ensure the DB URL always uses the asyncpg driver.
        Providers like Neon give plain postgresql:// which loads psycopg2.
        Replace with postgresql+asyncpg:// for the async driver.
        """
        for prefix in ("postgresql://", "postgres://"):
            if v.startswith(prefix):
                return "postgresql+asyncpg://" + v[len(prefix):]
        return v

    # ------------------------------------------------------------------
    # JWT / Auth
    # ------------------------------------------------------------------
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # ------------------------------------------------------------------
    # Cookie settings
    # ------------------------------------------------------------------
    cookie_secure: bool = True
    cookie_httponly: bool = True
    cookie_samesite: str = "lax"

    # ------------------------------------------------------------------
    # Email (for verification / password-reset emails)
    # ------------------------------------------------------------------
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "noreply@example.com"
    app_base_url: str = "http://localhost:3000"

    # ------------------------------------------------------------------
    # Payment Providers
    # ------------------------------------------------------------------
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    default_payment_provider: str = "razorpay"
    product_payment_providers: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------
    app_name: str = "Niya API"
    debug: bool = False
    environment: str = "production"

    # ------------------------------------------------------------------
    # Products — list of product identifiers served by this backend
    # ------------------------------------------------------------------
    products: List[str] = ["alpha", "taskboard"]

    # ------------------------------------------------------------------
    # Rate Limiting
    # ------------------------------------------------------------------
    rate_limit_per_minute: int = 60

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    log_level: str = "INFO"

    # ------------------------------------------------------------------
    # CORS
    # ------------------------------------------------------------------
    cors_origins: List[str] = ["http://localhost:3000"]

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()


def get_settings() -> Settings:
    return settings
