"""Business logic for ticker search and watchlist management."""

from __future__ import annotations

import yfinance as yf
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tickers.models import Ticker, WatchlistItem
from app.shared.logging import get_logger

logger = get_logger(__name__)


def _get_or_create_ticker_data(symbol: str) -> dict:
    """Fetch ticker metadata from yfinance."""
    info = yf.Ticker(symbol).info
    if not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Ticker '{symbol}' not found")
    return {
        "symbol": symbol.upper(),
        "name": info.get("longName") or info.get("shortName") or symbol,
        "exchange": info.get("exchange"),
        "currency": info.get("currency", "USD"),
    }


def search_tickers(query: str) -> list[dict]:
    """Search tickers using yfinance screen (best effort)."""
    try:
        results = yf.Search(query, max_results=8).quotes
        return [
            {
                "symbol": r.get("symbol", ""),
                "name": r.get("longname") or r.get("shortname") or r.get("symbol", ""),
                "exchange": r.get("exchange"),
            }
            for r in results
            if r.get("symbol")
        ]
    except Exception:
        return []


class TickerService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _get_or_create(self, symbol: str) -> Ticker:
        """Return existing Ticker row or create one from yfinance."""
        result = await self.db.execute(select(Ticker).where(Ticker.symbol == symbol.upper()))
        ticker = result.scalar_one_or_none()
        if ticker:
            return ticker
        data = _get_or_create_ticker_data(symbol)
        ticker = Ticker(**data)
        self.db.add(ticker)
        await self.db.flush()
        logger.info("ticker_created", symbol=symbol)
        return ticker

    async def get_watchlist(self, user_id: str) -> list[WatchlistItem]:
        result = await self.db.execute(
            select(WatchlistItem)
            .where(WatchlistItem.user_id == user_id)
            .order_by(WatchlistItem.added_at.desc())
        )
        return list(result.scalars().all())

    async def add_to_watchlist(self, symbol: str, user_id: str) -> WatchlistItem:
        ticker = await self._get_or_create(symbol)
        existing = await self.db.execute(
            select(WatchlistItem).where(
                WatchlistItem.user_id == user_id,
                WatchlistItem.ticker_id == ticker.id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already in watchlist")
        item = WatchlistItem(user_id=user_id, ticker_id=ticker.id)
        self.db.add(item)
        await self.db.flush()
        return item

    async def remove_from_watchlist(self, symbol: str, user_id: str) -> None:
        result = await self.db.execute(
            select(WatchlistItem)
            .join(Ticker, Ticker.id == WatchlistItem.ticker_id)
            .where(WatchlistItem.user_id == user_id, Ticker.symbol == symbol.upper())
        )
        item = result.scalar_one_or_none()
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not in watchlist")
        await self.db.delete(item)
