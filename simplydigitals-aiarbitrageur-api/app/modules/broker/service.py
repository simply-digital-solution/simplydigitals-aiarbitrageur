"""Alpaca broker service — handles order execution and position tracking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.shared.config import get_settings
from app.shared.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AccountInfo:
    """Account details from Alpaca."""

    account_value: float
    buying_power: float
    cash: float
    portfolio_value: float


@dataclass
class PositionInfo:
    """Position details from Alpaca."""

    symbol: str
    qty: float
    avg_entry_price: float
    market_value: float
    unrealized_pl: float


@dataclass
class OrderInfo:
    """Order details from Alpaca."""

    order_id: str
    symbol: str
    qty: float
    side: str  # "buy" | "sell"
    limit_price: float | None
    status: str  # "pending_new" | "filled" | "canceled" | "rejected"
    filled_qty: float
    filled_avg_price: float | None


class AlpacaBrokerServiceError(Exception):
    """Base exception for Alpaca broker operations."""

    pass


class AlpacaBrokerService:
    """Interface to Alpaca trading API (paper trading by default)."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: Any = None
        self._connect()

    def _connect(self) -> None:
        """Initialize Alpaca API client."""
        try:
            import alpaca_trade_api as tradeapi

            self._client = tradeapi.REST(
                key_id=self.settings.ALPACA_API_KEY,
                secret_key=self.settings.ALPACA_SECRET_KEY,
                base_url=self.settings.ALPACA_BASE_URL,
            )
            logger.info("alpaca_connected", base_url=self.settings.ALPACA_BASE_URL)
        except ImportError:
            logger.warning("alpaca_package_missing", hint="pip install alpaca-trade-api")
            self._client = None
        except Exception as exc:
            raise AlpacaBrokerServiceError(f"Failed to connect to Alpaca: {exc}")

    def get_account(self) -> AccountInfo:
        """Fetch account balance and buying power."""
        if self._client is None:
            raise AlpacaBrokerServiceError("Alpaca client not available (package not installed)")
        try:
            account = self._client.get_account()
            return AccountInfo(
                account_value=float(account.account_value),
                buying_power=float(account.buying_power),
                cash=float(account.cash),
                portfolio_value=float(account.portfolio_value),
            )
        except Exception as exc:
            raise AlpacaBrokerServiceError(f"Failed to fetch account: {exc}")

    def get_positions(self) -> list[PositionInfo]:
        """Fetch all open positions."""
        try:
            positions = self._client.list_positions()
            return [
                PositionInfo(
                    symbol=pos.symbol,
                    qty=float(pos.qty),
                    avg_entry_price=float(pos.avg_entry_price),
                    market_value=float(pos.market_value),
                    unrealized_pl=float(pos.unrealized_pl),
                )
                for pos in positions
            ]
        except Exception as exc:
            raise AlpacaBrokerServiceError(f"Failed to fetch positions: {exc}")

    def submit_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        limit_price: float | None = None,
    ) -> OrderInfo:
        """Submit a limit or market order.

        Args:
            symbol: Ticker symbol (e.g., "AAPL")
            qty: Quantity to trade
            side: "buy" or "sell"
            limit_price: Limit price (if None, market order)

        Returns:
            OrderInfo with order_id and status
        """
        try:
            order_params = {
                "symbol": symbol,
                "qty": qty,
                "side": side,
                "type": "limit" if limit_price else "market",
            }
            if limit_price:
                order_params["limit_price"] = limit_price

            order = self._client.submit_order(**order_params)
            logger.info(
                "order_submitted",
                symbol=symbol,
                qty=qty,
                side=side,
                limit_price=limit_price,
                order_id=order.id,
                status=order.status,
            )
            return OrderInfo(
                order_id=order.id,
                symbol=order.symbol,
                qty=float(order.qty),
                side=order.side,
                limit_price=limit_price,
                status=order.status,
                filled_qty=float(order.filled_qty),
                filled_avg_price=float(order.filled_avg_price) if order.filled_avg_price else None,
            )
        except Exception as exc:
            raise AlpacaBrokerServiceError(f"Failed to submit order for {symbol}: {exc}")

    def cancel_order(self, order_id: str) -> None:
        """Cancel an open order."""
        try:
            self._client.cancel_order(order_id)
            logger.info("order_cancelled", order_id=order_id)
        except Exception as exc:
            raise AlpacaBrokerServiceError(f"Failed to cancel order {order_id}: {exc}")

    def get_order_status(self, order_id: str) -> OrderInfo:
        """Fetch current status of an order."""
        try:
            order = self._client.get_order(order_id)
            return OrderInfo(
                order_id=order.id,
                symbol=order.symbol,
                qty=float(order.qty),
                side=order.side,
                limit_price=float(order.limit_price) if order.limit_price else None,
                status=order.status,
                filled_qty=float(order.filled_qty),
                filled_avg_price=float(order.filled_avg_price) if order.filled_avg_price else None,
            )
        except Exception as exc:
            raise AlpacaBrokerServiceError(f"Failed to fetch order {order_id}: {exc}")
