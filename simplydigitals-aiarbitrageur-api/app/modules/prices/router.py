"""Price endpoints — history, intraday, and live quotes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.dependencies import get_current_user_id
from app.modules.prices.schemas import ClosingBar, IntradayBar, QuoteRead
from app.modules.prices.service import PriceService
from app.shared.database import get_db

router = APIRouter(prefix="/prices", tags=["prices"])


@router.get("/{symbol}/history", response_model=list[ClosingBar])
async def get_history(
    symbol: str,
    range: str = "1Y",
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user_id),
) -> list[ClosingBar]:
    rows = await PriceService(db).get_history(symbol, range)
    return [
        ClosingBar(
            date=r.date,
            open=r.open,
            high=r.high,
            low=r.low,
            close=r.close,
            volume=r.volume,
        )
        for r in rows
    ]


@router.get("/{symbol}/intraday", response_model=list[IntradayBar])
async def get_intraday(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user_id),
) -> list[IntradayBar]:
    rows = await PriceService(db).get_intraday(symbol)
    return [
        IntradayBar(ts=r.ts, open=r.open, high=r.high, low=r.low, close=r.close, volume=r.volume)
        for r in rows
    ]


@router.get("/{symbol}/intraday-1min", response_model=list[IntradayBar])
async def get_intraday_1min(
    symbol: str,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user_id),
) -> list[IntradayBar]:
    """Fetch 1-minute bars for the last trading day. Limit=100 by default."""
    rows = await PriceService(db).get_intraday_1min(symbol, limit)
    return [
        IntradayBar(ts=r.ts, open=r.open, high=r.high, low=r.low, close=r.close, volume=r.volume)
        for r in rows
    ]


@router.get("/quotes", response_model=dict[str, QuoteRead])
async def get_quotes(
    symbols: str,
    _: str = Depends(get_current_user_id),
) -> dict[str, QuoteRead]:
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    raw = PriceService.get_quotes(symbol_list)
    return {
        sym: QuoteRead(symbol=sym, price=q["price"], change=q["change"], change_pct=q["changePct"])
        for sym, q in raw.items()
    }
