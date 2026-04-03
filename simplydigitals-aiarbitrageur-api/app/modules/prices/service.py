"""Price data service — fetch from yfinance, persist to DB."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta

if sys.version_info >= (3, 11):
    from datetime import UTC
else:
    from datetime import timezone
    UTC = timezone.utc

import yfinance as yf
from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.prices.models import ClosingPrice, IntradayPrice, IntradayPrice1Min
from app.modules.tickers.models import Ticker
from app.shared.config import get_settings
from app.shared.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Map UI range strings to yfinance period / interval
_RANGE_MAP = {
    "1D":  ("1d",  "5m"),
    "5D":  ("5d",  "5m"),
    "1M":  ("1mo", "1d"),
    "3M":  ("3mo", "1d"),
    "1Y":  ("1y",  "1d"),
    "2Y":  ("2y",  "1wk"),
    "5Y":  ("5y",  "1wk"),
}


class PriceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _get_ticker(self, symbol: str) -> Ticker:
        result = await self.db.execute(select(Ticker).where(Ticker.symbol == symbol.upper()))
        ticker = result.scalar_one_or_none()
        if not ticker:
            ticker = Ticker(symbol=symbol.upper(), name=symbol.upper())
            self.db.add(ticker)
            await self.db.flush()
        return ticker

    # ── History (closing prices) ────────────────────────────────────────────

    async def get_history(self, symbol: str, range_key: str = "1Y") -> list[ClosingPrice]:
        """Return closing prices from DB; backfill from yfinance if needed."""
        ticker = await self._get_ticker(symbol)
        period, _ = _RANGE_MAP.get(range_key, ("1y", "1d"))

        # Try DB first
        result = await self.db.execute(
            select(ClosingPrice)
            .where(ClosingPrice.ticker_id == ticker.id)
            .order_by(ClosingPrice.date.asc())
        )
        rows = list(result.scalars().all())

        if not rows:
            rows = await self._backfill_history(ticker, period)

        return rows

    async def _backfill_history(self, ticker: Ticker, period: str) -> list[ClosingPrice]:
        df = yf.Ticker(ticker.symbol).history(period=period, interval="1d", auto_adjust=True)
        if df.empty:
            return []
        rows = []
        for ts, row in df.iterrows():
            cp = ClosingPrice(
                ticker_id=ticker.id,
                date=ts.date(),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=int(row["Volume"]) if row["Volume"] else None,
            )
            self.db.add(cp)
            rows.append(cp)
        await self.db.flush()
        logger.info("history_backfilled", symbol=ticker.symbol, rows=len(rows))
        return rows

    # ── Intraday (5-min bars) ───────────────────────────────────────────────

    async def get_intraday(self, symbol: str) -> list[IntradayPrice]:
        """Return 5-min bars for the last 5 trading days from DB; refresh from yfinance."""
        ticker = await self._get_ticker(symbol)
        await self._refresh_intraday(ticker)
        result = await self.db.execute(
            select(IntradayPrice)
            .where(IntradayPrice.ticker_id == ticker.id)
            .order_by(IntradayPrice.ts.asc())
        )
        return list(result.scalars().all())

    async def _refresh_intraday(self, ticker: Ticker) -> None:
        df = yf.Ticker(ticker.symbol).history(period="5d", interval="5m", auto_adjust=True)
        if df.empty:
            return
        for ts, row in df.iterrows():
            bar = IntradayPrice(
                ticker_id=ticker.id,
                ts=ts.to_pydatetime().replace(tzinfo=UTC) if ts.tzinfo is None else ts.to_pydatetime(),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=int(row["Volume"]) if row["Volume"] else None,
            )
            self.db.add(bar)
        try:
            await self.db.flush()
        except Exception:
            await self.db.rollback()

    # ── Live quotes ─────────────────────────────────────────────────────────

    @staticmethod
    def get_quotes(symbols: list[str]) -> dict[str, dict]:
        quotes: dict[str, dict] = {}
        for symbol in symbols:
            try:
                info = yf.Ticker(symbol).fast_info
                prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose") or 0
                price = info.get("lastPrice") or info.get("regularMarketPrice") or 0
                change = price - prev_close
                change_pct = (change / prev_close * 100) if prev_close else 0
                quotes[symbol] = {"price": price, "change": change, "changePct": change_pct}
            except Exception:
                quotes[symbol] = {"price": 0, "change": 0, "changePct": 0}
        return quotes

    # ── Scheduled jobs ──────────────────────────────────────────────────────

    @staticmethod
    async def purge_old_intraday(db: AsyncSession) -> int:
        """Delete intraday bars older than INTRADAY_RETENTION_DAYS. Returns row count."""
        cutoff = datetime.now(UTC) - timedelta(days=settings.INTRADAY_RETENTION_DAYS)
        result = await db.execute(
            delete(IntradayPrice).where(IntradayPrice.ts < cutoff)
        )
        await db.commit()
        count = result.rowcount
        logger.info("intraday_purged", rows=count)
        return count

    @staticmethod
    async def refresh_all_intraday(db: AsyncSession) -> None:
        """Fetch latest 5-min bars for every ticker that has a watchlist entry."""
        result = await db.execute(select(Ticker))
        tickers = list(result.scalars().all())
        svc = PriceService(db)
        for ticker in tickers:
            try:
                await svc._refresh_intraday(ticker)
                logger.info("intraday_refreshed", symbol=ticker.symbol)
            except Exception as exc:
                logger.warning("intraday_refresh_failed", symbol=ticker.symbol, error=str(exc))

    @staticmethod
    async def refresh_all_closing(db: AsyncSession) -> None:
        """Fetch today's closing price for every known ticker."""
        result = await db.execute(select(Ticker))
        tickers = list(result.scalars().all())
        for ticker in tickers:
            try:
                df = yf.Ticker(ticker.symbol).history(period="5d", interval="1d", auto_adjust=True)
                if df.empty:
                    continue
                last = df.iloc[-1]
                cp = ClosingPrice(
                    ticker_id=ticker.id,
                    date=df.index[-1].date(),
                    open=float(last["Open"]),
                    high=float(last["High"]),
                    low=float(last["Low"]),
                    close=float(last["Close"]),
                    volume=int(last["Volume"]) if last["Volume"] else None,
                )
                db.add(cp)
            except Exception as exc:
                logger.warning("closing_refresh_failed", symbol=ticker.symbol, error=str(exc))
        try:
            await db.commit()
        except Exception:
            await db.rollback()

    # ── Intraday 1-minute bars ──────────────────────────────────────────────

    async def get_intraday_1min(self, symbol: str, limit: int = 100) -> list[IntradayPrice1Min]:
        """Return 1-min bars for the last trading day from DB; refresh from Alpaca/yfinance."""
        ticker = await self._get_ticker(symbol)
        await self._refresh_intraday_1min(ticker)

        # Return latest N bars
        result = await self.db.execute(
            select(IntradayPrice1Min)
            .where(IntradayPrice1Min.ticker_id == ticker.id)
            .order_by(IntradayPrice1Min.ts.desc())
            .limit(limit)
        )
        rows = list(result.scalars().all())
        rows.reverse()  # Return in ascending chronological order
        return rows

    async def _refresh_intraday_1min(self, ticker: Ticker) -> None:
        """Fetch latest 1-min bars from yfinance and upsert to DB."""
        try:
            df = yf.Ticker(ticker.symbol).history(period="1d", interval="1m", auto_adjust=True)
            if df.empty:
                return

            for ts, row in df.iterrows():
                bar = IntradayPrice1Min(
                    ticker_id=ticker.id,
                    ts=ts.to_pydatetime().replace(tzinfo=UTC) if ts.tzinfo is None else ts.to_pydatetime(),
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=int(row["Volume"]) if row["Volume"] else None,
                )
                self.db.add(bar)

            try:
                await self.db.flush()
            except Exception:
                await self.db.rollback()
        except Exception as exc:
            logger.warning("intraday_1min_refresh_failed", symbol=ticker.symbol, error=str(exc))

    @staticmethod
    async def purge_old_intraday_1min(db: AsyncSession) -> int:
        """Delete 1-min intraday bars older than INTRADAY_RETENTION_DAYS. Returns row count."""
        cutoff = datetime.now(UTC) - timedelta(days=settings.INTRADAY_RETENTION_DAYS)
        result = await db.execute(
            delete(IntradayPrice1Min).where(IntradayPrice1Min.ts < cutoff)
        )
        await db.commit()
        count = result.rowcount
        logger.info("intraday_1min_purged", rows=count)
        return count

    @staticmethod
    async def refresh_all_intraday_1min(db: AsyncSession) -> None:
        """Fetch latest 1-min bars for every ticker."""
        result = await db.execute(select(Ticker))
        tickers = list(result.scalars().all())
        svc = PriceService(db)
        for ticker in tickers:
            try:
                await svc._refresh_intraday_1min(ticker)
                logger.info("intraday_1min_refreshed", symbol=ticker.symbol)
            except Exception as exc:
                logger.warning("intraday_1min_refresh_failed", symbol=ticker.symbol, error=str(exc))
