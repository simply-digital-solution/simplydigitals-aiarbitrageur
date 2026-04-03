"""Arbitrageur API — application settings."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    # Application
    APP_NAME: str = "AI Arbitrageur API"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: Literal["development", "testing", "production"] = "development"

    # Security — must match the AIConnoisseur API secret (shared JWT)
    SECRET_KEY: str = Field(default="dev-shared-secret-must-match-aiconnoisseur!!", min_length=32)
    ALGORITHM: str = "HS256"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./arbitrageur_dev.db"

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60

    # Price data provider ("yfinance" | "alphavantage" | "polygon")
    PRICE_PROVIDER: str = "yfinance"
    ALPHAVANTAGE_API_KEY: str = ""
    POLYGON_API_KEY: str = ""

    # Intraday retention (days before auto-purge)
    INTRADAY_RETENTION_DAYS: int = 30

    # Alpaca Broker (paper trading)
    ALPACA_API_KEY: str = ""
    ALPACA_SECRET_KEY: str = ""
    ALPACA_BASE_URL: str = "https://paper-api.alpaca.markets"  # Paper trading endpoint

    # Trade Execution Limits
    MAX_POSITION_EXPOSURE_PCT: float = 10.0  # Max % of portfolio in single position
    MAX_DAILY_LOSS_PCT: float = 5.0  # Max daily loss before blocking trades
    MAX_ORDER_SIZE_PCT: float = 2.0  # Max order size as % of portfolio

    # AWS (Lambda + EventBridge)
    AWS_REGION: str = "ap-southeast-2"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
