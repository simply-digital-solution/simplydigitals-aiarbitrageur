"""Tests for Alpaca broker integration."""

from __future__ import annotations


def test_broker_service_methods() -> None:
    """Verify AlpacaBrokerService has all required methods."""
    from app.modules.broker.service import AlpacaBrokerService

    methods = [
        "get_account",
        "get_positions",
        "submit_order",
        "cancel_order",
        "get_order_status",
    ]

    for method in methods:
        assert hasattr(AlpacaBrokerService, method), f"AlpacaBrokerService missing method: {method}"


def test_broker_service_exception() -> None:
    """Verify AlpacaBrokerServiceError exception exists."""
    from app.modules.broker.service import AlpacaBrokerServiceError

    # Test it can be raised and caught
    try:
        raise AlpacaBrokerServiceError("test error")
    except AlpacaBrokerServiceError as e:
        assert str(e) == "test error"


def test_account_info_dataclass() -> None:
    """Verify AccountInfo dataclass structure."""
    from app.modules.broker.service import AccountInfo

    account = AccountInfo(
        portfolio_value=100000.0,
        buying_power=200000.0,
        cash=50000.0,
    )
    
    assert account.portfolio_value == 100000.0
    assert account.buying_power == 200000.0
    assert account.cash == 50000.0


def test_position_info_dataclass() -> None:
    """Verify PositionInfo dataclass structure."""
    from app.modules.broker.service import PositionInfo

    position = PositionInfo(
        symbol="AAPL",
        qty=100,
        avg_entry_price=150.0,
        market_value=15500.0,
        unrealized_pl=500.0,
    )
    
    assert position.symbol == "AAPL"
    assert position.qty == 100
    assert position.avg_entry_price == 150.0


def test_order_info_dataclass() -> None:
    """Verify OrderInfo dataclass structure."""
    from app.modules.broker.service import OrderInfo

    order = OrderInfo(
        order_id="order-123",
        status="filled",
        filled_qty=100,
        filled_avg_price=150.0,
    )
    
    assert order.order_id == "order-123"
    assert order.status == "filled"
    assert order.filled_qty == 100
