"""
Application configuration — loaded from environment variables / .env file.
"""

from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Environment Mode ---
    ENVIRONMENT: Literal["production", "sandbox", "mock"] = "mock"

    # --- Amazon SP-API Credentials ---
    SP_API_REFRESH_TOKEN: str = ""
    SP_API_CLIENT_ID: str = ""
    SP_API_CLIENT_SECRET: str = ""
    SP_API_AWS_ACCESS_KEY: str = ""
    SP_API_AWS_SECRET_KEY: str = ""
    SP_API_ROLE_ARN: str = ""
    SP_API_MARKETPLACE_ID: str = "ATVPDKIKX0DER"  # US default
    SP_API_REGION: str = "NA"

    # --- Safety ---
    DRY_RUN: bool = True  # Default safe: no real mutating calls

    # --- Database ---
    DATABASE_URL: str = "sqlite+aiosqlite:///./mcf.db"

    # --- Sync Settings ---
    INVENTORY_SYNC_INTERVAL_HOURS: int = 3
    ORDER_POLL_INTERVAL_MINUTES: int = 10  # 5-15 min range

    # --- Quicklly Integration ---
    QUICKLLY_API_URL: str = ""
    QUICKLLY_API_KEY: str = ""
    QUICKLLY_PUSH_ENABLED: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# Singleton — import this wherever needed
settings = Settings()
