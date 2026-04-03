"""Pydantic schemas for portfolio."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TradeRequest(_Base):
    symbol: str
    side: Literal["buy", "sell"]
    qty: float
    price: float

    @field_validator("qty", "price")
    @classmethod
    def must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Must be positive")
        return v


class TradeWithLimitsRequest(_Base):
    """Execute trade with automatic limit validation."""

    symbol: str
    side: Literal["buy", "sell"]
    qty: float
    limit_price: float | None = None  # None for market order

    @field_validator("qty", "limit_price")
    @classmethod
    def must_be_positive(cls, v: float) -> float:
        if v is not None and v <= 0:
            raise ValueError("Must be positive")
        return v


class PositionRead(_Base):
    symbol: str
    qty: float
    avg_cost: float
    current_price: float | None = None
    current_value: float | None = None
    pnl: float | None = None
    pnl_pct: float | None = None


class TradeRead(_Base):
    id: str
    symbol: str
    side: str
    qty: float
    execution_price: float | None
    executed_at: datetime | None


class TradeWithStatusRead(_Base):
    """Trade with Alpaca order tracking."""

    id: str
    symbol: str
    order_id: str | None
    side: str
    qty: float
    limit_price: float | None
    execution_price: float | None
    status: str
    created_at: datetime
    executed_at: datetime | None
