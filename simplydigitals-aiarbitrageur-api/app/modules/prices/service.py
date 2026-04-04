"""Price data service — fetch from yfinance, persist to DB."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import yfinance as yf
from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import CursorResult
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


def _to_utc(ts: object) -> datetime:
    import pandas as pd
    dt: datetime = pd.Timestamp(ts).to_pydatetime()
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


class PriceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _get_ticker(self, symbol: str) -> Ticker:
        result = await self.db.execute(
            select(Ticker).where(Ticker.symbol == symbol.upper())
        )
        ticker = result.scalar_one_or_none()
        if not ticker:
            try:
                ticker = Ticker(symbol=symbol.upper(), name=symbol.upper())
                self.db.add(ticker)
                await self.db.flush()
            except Exception:
                await self.db.rollback()
                result = await self.db.execute(
                    select(Ticker).where(Ticker.symbol == symbol.upper())
                )
                ticker = result.scalar_one()
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
        loop = asyncio.get_event_loop()
        sym = ticker.symbol
        df = await loop.run_in_executor(
            None,
            lambda: yf.Ticker(sym).history(period=period, interval="1d", auto_adjust=True),
        )
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
        ticker_id = ticker.id  # capture before potential session expiry
        await self._refresh_intraday(ticker)
        result = await self.db.execute(
            select(IntradayPrice)
            .where(IntradayPrice.ticker_id == ticker_id)
            .order_by(IntradayPrice.ts.asc())
        )
        return list(result.scalars().all())

    async def _refresh_intraday(self, ticker: Ticker) -> None:
        loop = asyncio.get_event_loop()
        symbol = ticker.symbol
        ticker_id = ticker.id
        df = await loop.run_in_executor(
            None,
            lambda: yf.Ticker(symbol).history(period="5d", interval="5m", auto_adjust=True),
        )
        if df.empty:
            return
        rows = [
            {
                "id": str(uuid.uuid4()),
                "ticker_id": ticker_id,
                "ts": _to_utc(ts),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": int(row["Volume"]) if row["Volume"] else None,
            }
            for ts, row in df.iterrows()
        ]
        stmt = sqlite_insert(IntradayPrice).values(rows).on_conflict_do_nothing()
        await self.db.execute(stmt)

    # ── Live quotes ─────────────────────────────────────────────────────────

    @staticmethod
    def get_quotes(symbols: list[str]) -> dict[str, dict]:  # type: ignore[type-arg]
        quotes: dict[str, dict] = {}  # type: ignore[type-arg]
        for symbol in symbols:
            try:
                info = yf.Ticker(symbol).fast_info
                prev_close = (
                    info.get("previousClose")
                    or info.get("regularMarketPreviousClose")
                    or 0
                )
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
        result: CursorResult[tuple[()]] = await db.execute(  # type: ignore[assignment]
            delete(IntradayPrice).where(IntradayPrice.ts < cutoff)
        )
        await db.commit()
        count = int(result.rowcount)
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
                loop = asyncio.get_event_loop()
                sym = ticker.symbol
                df = await loop.run_in_executor(
                    None,
                    lambda t=sym: yf.Ticker(t).history(  # type: ignore[misc]
                        period="5d", interval="1d", auto_adjust=True
                    ),
                )
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
        ticker_id = ticker.id  # capture before potential session expiry
        await self._refresh_intraday_1min(ticker)

        # Return latest N bars
        result = await self.db.execute(
            select(IntradayPrice1Min)
            .where(IntradayPrice1Min.ticker_id == ticker_id)
            .order_by(IntradayPrice1Min.ts.desc())
            .limit(limit)
        )
        rows = list(result.scalars().all())
        rows.reverse()  # Return in ascending chronological order
        return rows

    async def _refresh_intraday_1min(self, ticker: Ticker) -> None:
        """Fetch latest 1-min bars from yfinance and upsert to DB."""
        try:
            loop = asyncio.get_event_loop()
            symbol = ticker.symbol
            ticker_id = ticker.id
            df = await loop.run_in_executor(
                None,
                lambda: yf.Ticker(symbol).history(period="1d", interval="1m", auto_adjust=True),
            )
            if df.empty:
                return

            rows = [
                {
                    "id": str(uuid.uuid4()),
                    "ticker_id": ticker_id,
                    "ts": _to_utc(ts),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"]) if row["Volume"] else None,
                }
                for ts, row in df.iterrows()
            ]
            stmt = sqlite_insert(IntradayPrice1Min).values(rows).on_conflict_do_nothing()
            await self.db.execute(stmt)
        except Exception as exc:
            logger.warning("intraday_1min_refresh_failed", symbol=ticker.symbol, error=str(exc))

    @staticmethod
    async def purge_old_intraday_1min(db: AsyncSession) -> int:
        """Delete 1-min intraday bars older than INTRADAY_RETENTION_DAYS. Returns row count."""
        cutoff = datetime.now(UTC) - timedelta(days=settings.INTRADAY_RETENTION_DAYS)
        result: CursorResult[tuple[()]] = await db.execute(  # type: ignore[assignment]
            delete(IntradayPrice1Min).where(IntradayPrice1Min.ts < cutoff)
        )
        await db.commit()
        count = int(result.rowcount)
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
                logger.warning(
                    "intraday_1min_refresh_failed", symbol=ticker.symbol, error=str(exc)
                )
