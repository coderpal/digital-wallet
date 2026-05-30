"""
Configuration Management
------------------------
Single source of truth for all application settings.
Uses pydantic-settings to read from environment variables and .env file.
All settings are type-validated at startup — if a required variable is
missing or the wrong type, the app will fail immediately with a clear error
rather than silently misbehaving at runtime.
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Pydantic validates every field on startup. Required fields (no default)
    will raise a ValidationError if not provided in the environment,
    which prevents the app from starting with a broken configuration.
    """

    # ── Database ─────────────────────────────────────────────────────────────
    # Full PostgreSQL connection string including credentials.
    # Format: postgresql://user:password@host:port/dbname
    DATABASE_URL: str

    # ── JWT Authentication ────────────────────────────────────────────────────
    # SECRET_KEY is used to sign JWT tokens. In production this must be a
    # long, randomly generated string. If leaked, attackers can forge tokens.
    SECRET_KEY: str

    # Algorithm used to sign JWT tokens. HS256 is HMAC with SHA-256 —
    # a symmetric algorithm meaning the same key signs and verifies.
    ALGORITHM: str = "HS256"

    # How long an access token is valid in minutes.
    # Short expiry limits damage if a token is stolen.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # How long a refresh token is valid in days.
    # Refresh tokens are used to get new access tokens without re-logging in.
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Application ───────────────────────────────────────────────────────────
    APP_ENV: str = "development"       # "development" | "staging" | "production"
    APP_NAME: str = "Digital Wallet API"
    APP_VERSION: str = "1.0.0"

    # When DEBUG is True, SQLAlchemy logs all SQL queries to stdout.
    # Must be False in production — logs can contain sensitive data.
    DEBUG: bool = True

    # ── CORS ──────────────────────────────────────────────────────────────────
    # Comma-separated list of allowed frontend origins.
    # Example: "http://localhost:3000,https://yourfrontend.com"
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    @property
    def allowed_origins_list(self) -> List[str]:
        """
        Converts the comma-separated ALLOWED_ORIGINS string into a list.
        Strips whitespace from each origin to handle accidental spaces.
        Example: "http://localhost:3000, https://app.com" →
                 ["http://localhost:3000", "https://app.com"]
        """
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

    @property
    def is_production(self) -> bool:
        """
        Returns True when running in production environment.
        Used to conditionally disable API docs, enable stricter logging, etc.
        """
        return self.APP_ENV == "production"

    class Config:
        # Tell pydantic where to load environment variables from.
        # Variables defined in the actual environment take precedence over .env.
        env_file = ".env"

        # Treat variable names as case-sensitive.
        # Prevents DATABASE_URL and database_url from being treated as the same.
        case_sensitive = True


# Module-level singleton — import this instance everywhere.
# Initialised once at startup; never reinstantiated.
# Usage: from app.config import settings
settings = Settings()