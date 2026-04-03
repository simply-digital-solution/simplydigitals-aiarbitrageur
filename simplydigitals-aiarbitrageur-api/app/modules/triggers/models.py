"""ORM models for trade/alert triggers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class Trigger(Base):
    """A price condition that fires an alert or automatic trade."""

    __tablename__ = "triggers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    ticker_id: Mapped[str | None] = mapped_column(ForeignKey("tickers.id"), nullable=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)

    # Condition: "price_gte" | "price_lte" | "change_pct_gte" | "change_pct_lte"
    condition_type: Mapped[str] = mapped_column(String(20), nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)

    # Action: "alert" | "buy" | "sell"
    action: Mapped[str] = mapped_column(String(10), nullable=False, default="alert")
    qty: Mapped[float | None] = mapped_column(Float)

    # Status: "active" | "paused" | "fired"
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="active")
    fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    ticker: Mapped["Ticker"] = relationship()  # type: ignore[name-defined]
