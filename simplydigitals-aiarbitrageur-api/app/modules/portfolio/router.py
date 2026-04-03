"""Portfolio endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.dependencies import get_current_user_id
from app.modules.portfolio.schemas import (
    PositionRead,
    TradeRead,
    TradeRequest,
    TradeWithLimitsRequest,
    TradeWithStatusRead,
)
from app.modules.portfolio.service import PortfolioService
from app.shared.database import get_db

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("", response_model=list[PositionRead])
async def get_portfolio(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> list[PositionRead]:
    return await PortfolioService(db).get_portfolio(user_id)


@router.post("/trade", response_model=TradeRead, status_code=201)
async def execute_trade(
    req: TradeRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> TradeRead:
    trade = await PortfolioService(db).execute_trade(req, user_id)
    return TradeRead.model_validate(trade)


@router.post("/trade-with-limits", response_model=TradeWithStatusRead, status_code=201)
async def execute_trade_with_limits(
    req: TradeWithLimitsRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> TradeWithStatusRead:
    """Execute trade with automatic limit validation (dollar amount + position exposure)."""
    trade = await PortfolioService(db).execute_trade_with_limits(req, user_id)
    return TradeWithStatusRead.model_validate(trade)


@router.post("/sync-positions", status_code=200)
async def sync_positions_from_alpaca(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict[str, str]:
    """Manually sync Alpaca positions into local portfolio."""
    await PortfolioService(db).sync_positions_from_alpaca(user_id)
    return {"status": "positions synced"}
