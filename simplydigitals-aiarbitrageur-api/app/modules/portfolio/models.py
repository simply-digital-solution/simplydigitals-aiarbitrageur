"""ORM models for portfolio positions and trade history."""

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


class PortfolioPosition(Base):
    """Aggregate position per user per ticker (qty + avg cost)."""

    __tablename__ = "portfolio_positions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    avg_cost: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class Trade(Base):
    """Individual buy / sell records (tracked with Alpaca order_id)."""

    __tablename__ = "trades"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    ticker_id: Mapped[str | None] = mapped_column(ForeignKey("tickers.id"), nullable=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    order_id: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    side: Mapped[str] = mapped_column(String(4), nullable=False)   # "buy" | "sell"
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    limit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    execution_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    ticker: Mapped[Ticker] = relationship()  # type: ignore[name-defined]


class UserAccount(Base):
    """Per-user cash balance, updated on every trade."""

    __tablename__ = "user_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    cash: Mapped[float] = mapped_column(Float, nullable=False, default=100000.0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class TradeLimit(Base):
    """Per-user trading limits and risk parameters."""

    __tablename__ = "trade_limits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    max_position_exposure_pct: Mapped[float] = mapped_column(Float, default=10.0)
    max_daily_loss_pct: Mapped[float] = mapped_column(Float, default=5.0)
    max_order_size_pct: Mapped[float] = mapped_column(Float, default=2.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
