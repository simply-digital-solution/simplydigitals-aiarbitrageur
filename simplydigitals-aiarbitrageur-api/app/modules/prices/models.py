"""ORM models for closing prices and intraday prices."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class ClosingPrice(Base):
    """One row per ticker per calendar day. Stored permanently."""

    __tablename__ = "closing_prices"
    __table_args__ = (UniqueConstraint("ticker_id", "date"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    ticker_id: Mapped[str] = mapped_column(ForeignKey("tickers.id"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[float | None] = mapped_column(Float)
    high: Mapped[float | None] = mapped_column(Float)
    low: Mapped[float | None] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[int | None] = mapped_column(Integer)

    ticker: Mapped[Ticker] = relationship(back_populates="closing_prices")  # type: ignore[name-defined]


class IntradayPrice(Base):
    """5-minute bars. Auto-deleted after INTRADAY_RETENTION_DAYS days."""

    __tablename__ = "intraday_prices"
    __table_args__ = (UniqueConstraint("ticker_id", "ts"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    ticker_id: Mapped[str] = mapped_column(ForeignKey("tickers.id"), nullable=False, index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    open: Mapped[float | None] = mapped_column(Float)
    high: Mapped[float | None] = mapped_column(Float)
    low: Mapped[float | None] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[int | None] = mapped_column(Integer)

    ticker: Mapped[Ticker] = relationship(back_populates="intraday_prices")  # type: ignore[name-defined]


class IntradayPrice1Min(Base):
    """1-minute bars. Auto-deleted after INTRADAY_RETENTION_DAYS days."""

    __tablename__ = "intraday_1min_prices"
    __table_args__ = (UniqueConstraint("ticker_id", "ts"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    ticker_id: Mapped[str] = mapped_column(ForeignKey("tickers.id"), nullable=False, index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    open: Mapped[float | None] = mapped_column(Float)
    high: Mapped[float | None] = mapped_column(Float)
    low: Mapped[float | None] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[int | None] = mapped_column(Integer)

    ticker: Mapped[Ticker] = relationship(back_populates="intraday_1min_prices")  # type: ignore[name-defined]
