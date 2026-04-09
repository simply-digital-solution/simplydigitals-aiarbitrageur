"""Ticker search and watchlist endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.dependencies import get_current_user_id
from app.modules.tickers.schemas import TickerRead, TickerSearchResult, WatchlistItemRead
from app.modules.tickers.service import TickerService, search_tickers
from app.shared.database import get_db

router = APIRouter(prefix="/tickers", tags=["tickers"])
watchlist_router = APIRouter(prefix="/watchlist", tags=["watchlist"])


@router.get("/search", response_model=list[TickerSearchResult])
async def search(
    q: str,
    _: str = Depends(get_current_user_id),
) -> list[TickerSearchResult]:
    results = search_tickers(q)
    return [TickerSearchResult(**r) for r in results]  # type: ignore[arg-type]


@router.get("/{symbol}", response_model=TickerRead)
async def get_ticker(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user_id),
) -> TickerRead:
    ticker = await TickerService(db).get_ticker(symbol)
    await db.commit()
    return TickerRead(
        id=ticker.id,
        symbol=ticker.symbol,
        name=ticker.name,
        long_name=ticker.long_name,
        exchange=ticker.exchange,
        exchange_display=ticker.exchange_display,
        type_display=ticker.type_display,
        currency=ticker.currency,
    )


@watchlist_router.get("", response_model=list[WatchlistItemRead])
async def get_watchlist(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> list[WatchlistItemRead]:
    items = await TickerService(db).get_watchlist(user_id)
    return [
        WatchlistItemRead(
            id=item.id,
            symbol=item.ticker.symbol,
            name=item.ticker.name,
            long_name=item.ticker.long_name,
            exchange=item.ticker.exchange,
            exchange_display=item.ticker.exchange_display,
            type_display=item.ticker.type_display,
            added_at=item.added_at,
        )
        for item in items
    ]


@watchlist_router.post("/{symbol}", response_model=WatchlistItemRead, status_code=201)
async def add_to_watchlist(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> WatchlistItemRead:
    item = await TickerService(db).add_to_watchlist(symbol, user_id)
    return WatchlistItemRead(
        id=item.id,
        symbol=item.ticker.symbol,
        name=item.ticker.name,
        long_name=item.ticker.long_name,
        exchange=item.ticker.exchange,
        exchange_display=item.ticker.exchange_display,
        type_display=item.ticker.type_display,
        added_at=item.added_at,
    )


@watchlist_router.delete("/{symbol}", status_code=204)
async def remove_from_watchlist(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> None:
    await TickerService(db).remove_from_watchlist(symbol, user_id)
