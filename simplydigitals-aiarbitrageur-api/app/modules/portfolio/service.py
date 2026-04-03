"""Portfolio service — positions, trades, and live P&L."""

from __future__ import annotations

import yfinance as yf
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.broker.service import AlpacaBrokerService, AlpacaBrokerServiceError
from app.modules.portfolio.models import PortfolioPosition, Trade, TradeLimit, UserAccount
from app.modules.portfolio.schemas import PositionRead, TradeRequest, TradeWithLimitsRequest
from app.shared.logging import get_logger

logger = get_logger(__name__)


def _live_price(symbol: str) -> float | None:
    try:
        info = yf.Ticker(symbol).fast_info
        price = info.get("lastPrice") or info.get("regularMarketPrice")
        return float(price) if price else None
    except Exception:
        return None


class PortfolioService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._broker: AlpacaBrokerService | None = None

    @property
    def broker(self) -> AlpacaBrokerService:
        if self._broker is None:
            self._broker = AlpacaBrokerService()
        return self._broker

    async def get_portfolio(self, user_id: str) -> list[PositionRead]:
        result = await self.db.execute(
            select(PortfolioPosition).where(PortfolioPosition.user_id == user_id)
        )
        positions = list(result.scalars().all())
        out = []
        for pos in positions:
            if pos.qty <= 0:
                continue
            price = _live_price(pos.symbol)
            current_value = (price * pos.qty) if price else None
            cost_basis = pos.avg_cost * pos.qty
            pnl = (current_value - cost_basis) if current_value is not None else None
            pnl_pct = (pnl / cost_basis * 100) if (pnl is not None and cost_basis) else None
            out.append(
                PositionRead(
                    symbol=pos.symbol,
                    qty=pos.qty,
                    avg_cost=pos.avg_cost,
                    current_price=price,
                    current_value=current_value,
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                )
            )
        return out

    async def execute_trade(self, req: TradeRequest, user_id: str) -> Trade:
        symbol = req.symbol.upper()
        account = await self._get_or_create_account(user_id)
        trade_value = req.price * req.qty

        result = await self.db.execute(
            select(PortfolioPosition).where(
                PortfolioPosition.user_id == user_id,
                PortfolioPosition.symbol == symbol,
            )
        )
        position = result.scalar_one_or_none()

        if req.side == "buy":
            if account.cash < trade_value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient cash: have ${account.cash:.2f}, need ${trade_value:.2f}",
                )
            account.cash -= trade_value
            if position:
                total_cost = position.avg_cost * position.qty + req.price * req.qty
                position.qty += req.qty
                position.avg_cost = total_cost / position.qty
            else:
                position = PortfolioPosition(
                    user_id=user_id,
                    symbol=symbol,
                    qty=req.qty,
                    avg_cost=req.price,
                )
                self.db.add(position)
        else:
            # sell
            if not position or position.qty < req.qty:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient position: have {position.qty if position else 0}, selling {req.qty}",
                )
            position.qty -= req.qty
            account.cash += trade_value
            if position.qty == 0:
                await self.db.delete(position)

        trade = Trade(
            user_id=user_id,
            symbol=symbol,
            side=req.side,
            qty=req.qty,
            limit_price=req.price,
            execution_price=req.price,
        )
        self.db.add(trade)
        await self.db.flush()
        logger.info("trade_executed", symbol=symbol, side=req.side, qty=req.qty, price=req.price)
        return trade

    async def _get_or_create_trade_limits(self, user_id: str) -> TradeLimit:
        """Get existing trade limits or create default ones."""
        result = await self.db.execute(
            select(TradeLimit).where(TradeLimit.user_id == user_id)
        )
        limits = result.scalar_one_or_none()
        if limits:
            return limits

        # Create default limits
        limits = TradeLimit(user_id=user_id)
        self.db.add(limits)
        await self.db.flush()
        return limits

    async def _calculate_portfolio_exposure(self, user_id: str) -> dict[str, float]:
        """Calculate total portfolio exposure and account value.

        Returns:
            {
                'total_value': float,
                'current_exposure': float (total value of all positions),
                'cash': float,
            }
        """
        try:
            account = self.broker.get_account()
            current_exposure = account.portfolio_value - account.cash
            return {
                "total_value": account.portfolio_value,
                "current_exposure": max(current_exposure, 0),
                "cash": account.cash,
            }
        except AlpacaBrokerServiceError as exc:
            logger.error("portfolio_exposure_fetch_failed", error=str(exc))
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to calculate portfolio exposure",
            ) from exc

    async def execute_trade_with_limits(
        self, req: TradeWithLimitsRequest, user_id: str
    ) -> Trade:
        """Execute trade with automatic limit validation.

        Checks:
        1. Order size doesn't exceed max_order_size_pct
        2. Position exposure after trade doesn't exceed max_position_exposure_pct

        Raises HTTPException if limits violated.
        """
        symbol = req.symbol.upper()

        # Fetch trade limits
        limits = await self._get_or_create_trade_limits(user_id)

        # Calculate current portfolio state
        portfolio = await self._calculate_portfolio_exposure(user_id)
        total_value = portfolio["total_value"]

        # Get current price
        current_price = _live_price(symbol)
        if not current_price:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not fetch price for {symbol}",
            )

        # Estimate trade value
        trade_value = req.qty * current_price if req.limit_price is None else req.qty * req.limit_price

        # Check 1: Max order size
        max_order_value = total_value * (limits.max_order_size_pct / 100)
        if trade_value > max_order_value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Order size ${trade_value:.2f} exceeds max allowed ${max_order_value:.2f} ({limits.max_order_size_pct}% of portfolio)",
            )

        # Check 2: Position exposure (simplified)
        # After-trade exposure = current_exposure + order value (for buy)
        after_trade_exposure = portfolio["current_exposure"]
        if req.side == "buy":
            after_trade_exposure += trade_value
        elif req.side == "sell":
            after_trade_exposure = max(after_trade_exposure - trade_value, 0)

        max_exposure = total_value * (limits.max_position_exposure_pct / 100)
        if after_trade_exposure > max_exposure:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Trade would result in {after_trade_exposure/total_value*100:.1f}% exposure (max {limits.max_position_exposure_pct}%)",
            )

        # All limits passed; submit to Alpaca
        try:
            order_info = self.broker.submit_order(
                symbol=symbol,
                qty=req.qty,
                side=req.side,
                limit_price=req.limit_price,
            )

            # Store trade record with order tracking
            trade = Trade(
                user_id=user_id,
                symbol=symbol,
                order_id=order_info.order_id,
                side=req.side,
                qty=req.qty,
                limit_price=req.limit_price,
                status=order_info.status,
                execution_price=order_info.filled_avg_price,
            )
            self.db.add(trade)
            await self.db.flush()

            logger.info(
                "trade_with_limits_executed",
                symbol=symbol,
                qty=req.qty,
                side=req.side,
                order_id=order_info.order_id,
            )
            return trade
        except AlpacaBrokerServiceError as exc:
            logger.error("alpaca_order_submit_failed", error=str(exc))
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to submit order: {exc}",
            ) from exc

    async def _get_or_create_account(self, user_id: str) -> UserAccount:
        result = await self.db.execute(
            select(UserAccount).where(UserAccount.user_id == user_id)
        )
        account = result.scalar_one_or_none()
        if account:
            return account
        account = UserAccount(user_id=user_id, cash=100_000.0)
        self.db.add(account)
        await self.db.flush()
        return account

    async def get_account_info(self, user_id: str) -> dict:
        account = await self._get_or_create_account(user_id)
        result = await self.db.execute(
            select(PortfolioPosition).where(PortfolioPosition.user_id == user_id)
        )
        positions = list(result.scalars().all())
        positions_value = sum(
            ((_live_price(p.symbol) or p.avg_cost) * p.qty)
            for p in positions if p.qty > 0
        )
        return {
            "cash": account.cash,
            "buying_power": account.cash,
            "portfolio_value": account.cash + positions_value,
        }

    async def get_trades(self, user_id: str, limit: int = 50) -> list[Trade]:
        result = await self.db.execute(
            select(Trade)
            .where(Trade.user_id == user_id)
            .order_by(Trade.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def sync_positions_from_alpaca(self, user_id: str) -> None:
        """Fetch live positions from Alpaca and upsert to portfolio_positions table."""
        try:
            alpaca_positions = self.broker.get_positions()

            for pos in alpaca_positions:
                result = await self.db.execute(
                    select(PortfolioPosition).where(
                        PortfolioPosition.user_id == user_id,
                        PortfolioPosition.symbol == pos.symbol,
                    )
                )
                db_pos = result.scalar_one_or_none()

                if db_pos:
                    # Update existing position
                    db_pos.qty = pos.qty
                    db_pos.avg_cost = pos.avg_entry_price
                else:
                    # Create new position
                    db_pos = PortfolioPosition(
                        user_id=user_id,
                        symbol=pos.symbol,
                        qty=pos.qty,
                        avg_cost=pos.avg_entry_price,
                    )
                    self.db.add(db_pos)

            await self.db.flush()
            logger.info("positions_synced_from_alpaca", position_count=len(alpaca_positions))
        except AlpacaBrokerServiceError as exc:
            logger.error("sync_positions_failed", error=str(exc))
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to sync positions from Alpaca",
            ) from exc
