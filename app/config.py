"""
Configuration module using 12-factor environment variables.
"""
import os
from functools import lru_cache
from typing import Optional


class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self):
        self.database_url: str = os.getenv("DATABASE_URL", "sqlite:////data/app.db")
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()
        self.webhook_secret: Optional[str] = os.getenv("WEBHOOK_SECRET")

    @property
    def db_path(self) -> str:
        """Extract the file path from SQLite URL."""
        if self.database_url.startswith("sqlite:///"):
            return self.database_url.replace("sqlite:///", "")
        return "/data/app.db"

    def is_configured(self) -> bool:
        """Check if all required settings are present."""
        return bool(self.webhook_secret)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
