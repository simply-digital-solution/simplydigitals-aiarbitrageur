"""ORM models for tickers and watchlist."""

from __future__ import annotations

import sys
import uuid
from datetime import datetime

if sys.version_info >= (3, 11):
    from datetime import UTC
else:
    from datetime import timezone
    UTC = timezone.utc

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class Ticker(Base):
    __tablename__ = "tickers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    exchange: Mapped[str | None] = mapped_column(String(50))
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    watchlist_items: Mapped[list[WatchlistItem]] = relationship(back_populates="ticker")
    closing_prices: Mapped[list] = relationship("ClosingPrice", back_populates="ticker")
    intraday_prices: Mapped[list] = relationship("IntradayPrice", back_populates="ticker")
    intraday_1min_prices: Mapped[list] = relationship("IntradayPrice1Min", back_populates="ticker")


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (UniqueConstraint("user_id", "ticker_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    ticker_id: Mapped[str] = mapped_column(ForeignKey("tickers.id"), nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    ticker: Mapped[Ticker] = relationship(back_populates="watchlist_items")
