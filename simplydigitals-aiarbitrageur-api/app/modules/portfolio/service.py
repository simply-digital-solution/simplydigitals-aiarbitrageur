"""Portfolio service — positions, trades, and live P&L."""

from __future__ import annotations

from datetime import UTC, datetime

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
                    detail=(
                    f"Insufficient position: have {position.qty if position else 0}, "
                    f"selling {req.qty}"
                ),
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
        """Calculate total portfolio exposure and account value from local DB.

        Returns:
            {
                'total_value': float,
                'current_exposure': float (total value of all positions),
                'cash': float,
            }
        """
        account = await self._get_or_create_account(user_id)
        result = await self.db.execute(
            select(PortfolioPosition).where(PortfolioPosition.user_id == user_id)
        )
        positions = list(result.scalars().all())
        current_exposure = sum(
            ((_live_price(p.symbol) or p.avg_cost) * p.qty)
            for p in positions if p.qty > 0
        )
        total_value = account.cash + current_exposure
        return {
            "total_value": total_value,
            "current_exposure": current_exposure,
            "cash": account.cash,
        }

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
        trade_value = (
            req.qty * current_price if req.limit_price is None else req.qty * req.limit_price
        )

        # Check 1: Max order size
        max_order_value = total_value * (limits.max_order_size_pct / 100)
        if trade_value > max_order_value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Order size ${trade_value:.2f} exceeds max allowed "
                    f"${max_order_value:.2f} ({limits.max_order_size_pct}% of portfolio)"
                ),
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
                detail=(
                    f"Trade would result in {after_trade_exposure / total_value * 100:.1f}% "
                    f"exposure (max {limits.max_position_exposure_pct}%)"
                ),
            )

        # Step 1 — persist trade immediately as "not_sent" before touching Alpaca
        effective_price = req.limit_price if req.limit_price else float(current_price)
        trade_value = req.qty * effective_price

        account = await self._get_or_create_account(user_id)

        pos_result = await self.db.execute(
            select(PortfolioPosition).where(
                PortfolioPosition.user_id == user_id,
                PortfolioPosition.symbol == symbol,
            )
        )
        position = pos_result.scalar_one_or_none()

        if req.side == "buy":
            if account.cash < trade_value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient cash: have ${account.cash:.2f}, need ${trade_value:.2f}",
                )
            account.cash -= trade_value
            if position:
                total_cost = position.avg_cost * position.qty + effective_price * req.qty
                position.qty += req.qty
                position.avg_cost = total_cost / position.qty
            else:
                position = PortfolioPosition(
                    user_id=user_id, symbol=symbol, qty=req.qty, avg_cost=effective_price
                )
                self.db.add(position)
        else:
            if not position or position.qty < req.qty:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Insufficient position: have {position.qty if position else 0}, "
                        f"selling {req.qty}"
                    ),
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
            limit_price=req.limit_price,
            market_price=float(current_price),
            status="not_sent",
        )
        self.db.add(trade)
        await self.db.flush()
        logger.info("trade_created_not_sent", trade_id=trade.id, symbol=symbol)

        # Step 2 — send to Alpaca; update status to "reached" on ACK, "accepted" on fill
        if self.broker._client is not None:
            try:
                order_info = self.broker.submit_order(
                    symbol=symbol,
                    qty=req.qty,
                    side=req.side,
                    limit_price=req.limit_price,
                )
                trade.order_id = order_info.order_id
                # Alpaca acknowledged the order — mark as "reached"
                trade.status = "reached"

                # If Alpaca already filled it (market orders fill instantly)
                if order_info.status == "filled":
                    trade.status = "accepted"
                    trade.filled_qty = order_info.filled_qty or req.qty
                    trade.execution_price = order_info.filled_avg_price or effective_price
                    trade.executed_at = datetime.now(UTC)

                logger.info(
                    "trade_sent_to_alpaca",
                    trade_id=trade.id,
                    order_id=trade.order_id,
                    alpaca_status=order_info.status,
                )
            except AlpacaBrokerServiceError as exc:
                # Trade stays as "not_sent" in DB — caller can retry
                logger.error("alpaca_order_submit_failed", trade_id=trade.id, error=str(exc))
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Failed to submit order to Alpaca: {exc}",
                ) from exc
        else:
            # No Alpaca client — paper trade fills immediately
            trade.status = "accepted"
            trade.filled_qty = req.qty
            trade.execution_price = effective_price
            trade.executed_at = datetime.now(UTC)
            logger.info(
                "trade_paper_accepted",
                trade_id=trade.id,
                symbol=symbol,
                reason="alpaca_unavailable",
            )

        await self.db.flush()
        return trade

    async def refresh_trade_status(self, trade_id: str, user_id: str) -> Trade:
        """Poll Alpaca for the latest order status and update the local trade record.

        Status transitions:
          not_sent → reached  (Alpaca acknowledged)
          reached  → accepted (Alpaca filled)
        """
        result = await self.db.execute(
            select(Trade).where(Trade.id == trade_id, Trade.user_id == user_id)
        )
        trade = result.scalar_one_or_none()
        if not trade:
            raise HTTPException(status_code=404, detail="Trade not found")

        if not trade.order_id or self.broker._client is None:
            return trade

        try:
            order_info = self.broker.get_order_status(trade.order_id)
        except AlpacaBrokerServiceError as exc:
            logger.warning("alpaca_status_poll_failed", trade_id=trade_id, error=str(exc))
            return trade

        if order_info.status == "filled" and trade.status != "accepted":
            trade.status = "accepted"
            trade.filled_qty = order_info.filled_qty or trade.qty
            trade.execution_price = order_info.filled_avg_price or trade.execution_price
            trade.executed_at = datetime.now(UTC)
            logger.info("trade_accepted", trade_id=trade.id, order_id=trade.order_id)
        elif order_info.status == "partially_filled":
            trade.filled_qty = order_info.filled_qty
            if trade.status == "not_sent":
                trade.status = "reached"
            logger.info(
                "trade_partially_filled", trade_id=trade.id, filled_qty=order_info.filled_qty
            )
        elif order_info.status in ("accepted", "pending_new", "new"):
            if trade.status == "not_sent":
                trade.status = "reached"
                logger.info("trade_reached", trade_id=trade.id, order_id=trade.order_id)

        await self.db.flush()
        return trade

    async def cancel_trade(self, trade_id: str, user_id: str) -> Trade:
        """Cancel a trade that has not yet been accepted.

        - Cancels on Alpaca if an order_id exists
        - Reverses the local cash / position changes
        - Marks the trade status as "canceled"
        """
        result = await self.db.execute(
            select(Trade).where(Trade.id == trade_id, Trade.user_id == user_id)
        )
        trade = result.scalar_one_or_none()
        if not trade:
            raise HTTPException(status_code=404, detail="Trade not found")

        if trade.status in ("accepted", "canceled", "filled"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel a trade with status '{trade.status}'",
            )

        # Cancel on Alpaca if order was sent
        if trade.order_id and self.broker._client is not None:
            try:
                self.broker.cancel_order(trade.order_id)
            except AlpacaBrokerServiceError as exc:
                logger.error("alpaca_cancel_failed", trade_id=trade_id, error=str(exc))
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Failed to cancel order on Alpaca: {exc}",
                ) from exc

        # Reverse local cash / position
        effective_price = trade.limit_price or trade.market_price or 0.0
        trade_value = trade.qty * effective_price
        account = await self._get_or_create_account(user_id)

        pos_result = await self.db.execute(
            select(PortfolioPosition).where(
                PortfolioPosition.user_id == user_id,
                PortfolioPosition.symbol == trade.symbol,
            )
        )
        position = pos_result.scalar_one_or_none()

        if trade.side == "buy":
            # Reverse the cash debit
            account.cash += trade_value
            if position:
                position.qty -= trade.qty
                if position.qty <= 0:
                    await self.db.delete(position)
        else:
            # Reverse the cash credit
            account.cash -= trade_value
            if position:
                total_cost = position.avg_cost * position.qty + effective_price * trade.qty
                position.qty += trade.qty
                position.avg_cost = total_cost / position.qty
            else:
                position = PortfolioPosition(
                    user_id=user_id,
                    symbol=trade.symbol,
                    qty=trade.qty,
                    avg_cost=effective_price,
                )
                self.db.add(position)

        trade.status = "canceled"
        await self.db.flush()
        logger.info("trade_canceled", trade_id=trade.id, symbol=trade.symbol)
        return trade

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

    async def get_account_info(self, user_id: str) -> dict[str, object]:
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
                    db_pos.qty = pos.qty
                    db_pos.avg_cost = pos.avg_entry_price
                else:
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

    async def get_trade_sync_status(self, user_id: str) -> dict[str, object]:
        """Compare Alpaca filled orders against local trades to detect divergence.

        Returns:
            {
                "in_sync": bool,
                "alpaca_count": int,        # filled orders in Alpaca
                "local_count": int,         # locally tracked orders with an order_id
                "missing_count": int,       # Alpaca orders absent from local DB
                "alpaca_connected": bool,
            }
        """
        if self.broker._client is None:
            return {
                "in_sync": True,
                "alpaca_count": 0,
                "local_count": 0,
                "missing_count": 0,
                "alpaca_connected": False,
            }
        try:
            alpaca_orders = self.broker.get_orders(status="filled", limit=100)
            alpaca_ids = {o.order_id for o in alpaca_orders}

            existing_result = await self.db.execute(
                select(Trade.order_id).where(
                    Trade.user_id == user_id, Trade.order_id.isnot(None)
                )
            )
            local_ids = {row[0] for row in existing_result.all()}

            missing = alpaca_ids - local_ids
            return {
                "in_sync": len(missing) == 0,
                "alpaca_count": len(alpaca_ids),
                "local_count": len(local_ids),
                "missing_count": len(missing),
                "alpaca_connected": True,
            }
        except AlpacaBrokerServiceError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to check sync status: {exc}",
            ) from exc

    async def sync_trades_from_alpaca(self, user_id: str) -> dict[str, object]:
        """Import Alpaca filled orders that are not yet in the local trades table.

        Only imports orders missing from local DB — existing records are untouched.
        Returns the number of trades imported.
        """
        if self.broker._client is None:
            return {"imported": 0, "alpaca_connected": False}
        try:
            alpaca_orders = self.broker.get_orders(status="filled", limit=100)

            existing_result = await self.db.execute(
                select(Trade.order_id).where(
                    Trade.user_id == user_id, Trade.order_id.isnot(None)
                )
            )
            existing_ids = {row[0] for row in existing_result.all()}

            imported = 0
            for order in alpaca_orders:
                if order.order_id in existing_ids:
                    continue
                self.db.add(
                    Trade(
                        user_id=user_id,
                        symbol=order.symbol,
                        order_id=order.order_id,
                        side=order.side,
                        qty=order.filled_qty,
                        limit_price=order.limit_price,
                        execution_price=order.filled_avg_price,
                        status=order.status,
                    )
                )
                imported += 1

            await self.db.flush()
            logger.info("trades_synced_from_alpaca", imported=imported)
            return {"imported": imported, "alpaca_connected": True}
        except AlpacaBrokerServiceError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to sync trades: {exc}",
            ) from exc
