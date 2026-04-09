"""Pydantic schemas for triggers."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


ConditionType = Literal["price_gte", "price_lte", "change_pct_gte", "change_pct_lte"]
ActionType = Literal["alert", "buy", "sell"]
TriggerStatus = Literal["active", "paused", "fired"]


class TriggerCreate(_Base):
    symbol: str
    condition_type: ConditionType
    threshold: float
    action: ActionType = "alert"
    qty: float | None = None

    @field_validator("qty")
    @classmethod
    def qty_required_for_trade(cls, v: float | None, info: Any) -> float | None:
        action = info.data.get("action")
        if action in ("buy", "sell") and (v is None or v <= 0):
            raise ValueError("qty is required for buy/sell actions")
        return v


class TriggerUpdate(_Base):
    status: TriggerStatus | None = None
    threshold: float | None = None
    action: ActionType | None = None
    qty: float | None = None


class TriggerRead(_Base):
    id: str
    symbol: str
    condition_type: str
    threshold: float
    action: str
    qty: float | None = None
    status: str
    fired_at: datetime | None = None
    created_at: datetime
