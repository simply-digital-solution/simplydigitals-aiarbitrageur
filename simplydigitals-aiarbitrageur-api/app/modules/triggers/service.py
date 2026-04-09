"""Trigger service — CRUD and evaluation engine."""

from __future__ import annotations

from datetime import UTC, datetime

import yfinance as yf
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.triggers.models import Trigger
from app.modules.triggers.schemas import TriggerCreate, TriggerUpdate
from app.shared.logging import get_logger

logger = get_logger(__name__)


def _current_price(symbol: str) -> float | None:
    try:
        info = yf.Ticker(symbol).fast_info
        price = info.get("lastPrice") or info.get("regularMarketPrice")
        return float(price) if price else None
    except Exception:
        return None


def _condition_met(trigger: Trigger, price: float, prev_close: float | None) -> bool:
    t = trigger.condition_type
    v = trigger.threshold
    if t == "price_gte":
        return price >= v
    if t == "price_lte":
        return price <= v
    if t in ("change_pct_gte", "change_pct_lte") and prev_close:
        pct = (price - prev_close) / prev_close * 100
        if t == "change_pct_gte":
            return pct >= v
        return pct <= v
    return False


class TriggerService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_triggers(self, user_id: str) -> list[Trigger]:
        result = await self.db.execute(
            select(Trigger).where(Trigger.user_id == user_id).order_by(Trigger.created_at.desc())
        )
        return list(result.scalars().all())

    async def create(self, req: TriggerCreate, user_id: str) -> Trigger:
        trigger = Trigger(
            user_id=user_id,
            symbol=req.symbol.upper(),
            condition_type=req.condition_type,
            threshold=req.threshold,
            action=req.action,
            qty=req.qty,
        )
        self.db.add(trigger)
        await self.db.flush()
        logger.info("trigger_created", trigger_id=trigger.id, symbol=trigger.symbol)
        return trigger

    async def update(self, trigger_id: str, req: TriggerUpdate, user_id: str) -> Trigger:
        trigger = await self._get(trigger_id, user_id)
        for field, val in req.model_dump(exclude_none=True).items():
            setattr(trigger, field, val)
        await self.db.flush()
        return trigger

    async def delete(self, trigger_id: str, user_id: str) -> None:
        trigger = await self._get(trigger_id, user_id)
        await self.db.delete(trigger)

    async def _get(self, trigger_id: str, user_id: str) -> Trigger:
        result = await self.db.execute(
            select(Trigger).where(Trigger.id == trigger_id, Trigger.user_id == user_id)
        )
        trigger = result.scalar_one_or_none()
        if not trigger:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trigger not found")
        return trigger

    @staticmethod
    async def evaluate_all(db: AsyncSession) -> None:
        """Evaluate all active triggers and fire those whose conditions are met."""
        result = await db.execute(select(Trigger).where(Trigger.status == "active"))
        triggers = list(result.scalars().all())

        # Group by symbol to minimise yfinance calls
        by_symbol: dict[str, list[Trigger]] = {}
        for t in triggers:
            by_symbol.setdefault(t.symbol, []).append(t)

        for symbol, symbol_triggers in by_symbol.items():
            try:
                ticker = yf.Ticker(symbol)
                fast = ticker.fast_info
                price = fast.get("lastPrice") or fast.get("regularMarketPrice") or 0
                prev_close = fast.get("previousClose") or fast.get("regularMarketPreviousClose")
            except Exception:
                continue

            for trigger in symbol_triggers:
                if not _condition_met(trigger, price, prev_close):
                    continue

                trigger.status = "fired"
                trigger.fired_at = datetime.now(UTC)
                logger.info("trigger_fired", trigger_id=trigger.id, symbol=symbol, price=price)

                if trigger.action in ("buy", "sell") and trigger.qty:
                    # Import here to avoid circular imports
                    from app.modules.portfolio.schemas import TradeWithLimitsRequest
                    from app.modules.portfolio.service import PortfolioService
                    try:
                        svc = PortfolioService(db)
                        await svc.execute_trade_with_limits(
                            TradeWithLimitsRequest(
                                symbol=symbol,
                                side=trigger.action,  # type: ignore[arg-type]
                                qty=trigger.qty,
                                limit_price=price,  # Use current price as limit
                            ),
                            trigger.user_id,
                        )
                        logger.info(
                            "trigger_trade_executed",
                            trigger_id=trigger.id, symbol=symbol, qty=trigger.qty,
                        )
                    except Exception as exc:
                        logger.warning(
                            "trigger_trade_failed", trigger_id=trigger.id, error=str(exc)
                        )

        await db.commit()
