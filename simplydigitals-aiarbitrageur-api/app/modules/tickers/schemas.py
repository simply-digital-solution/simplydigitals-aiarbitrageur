"""Pydantic schemas for tickers and watchlist."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TickerRead(_Base):
    id: str
    symbol: str
    name: str
    exchange: str | None = None
    currency: str = "USD"


class TickerSearchResult(_Base):
    symbol: str
    name: str
    exchange: str | None = None
    exchange_display: str | None = None
    type_display: str | None = None


class WatchlistItemRead(_Base):
    id: str
    symbol: str
    name: str
    exchange: str | None = None
    added_at: datetime
