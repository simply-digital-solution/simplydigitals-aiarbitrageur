"""Pydantic schemas for price data."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ClosingBar(_Base):
    date: date
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float
    volume: int | None = None


class IntradayBar(_Base):
    ts: datetime
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float
    volume: int | None = None


class QuoteRead(_Base):
    symbol: str
    price: float
    change: float
    change_pct: float
