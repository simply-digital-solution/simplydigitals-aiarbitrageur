"""Tests for request and response schemas."""

from __future__ import annotations


def test_trade_with_limits_request_schema() -> None:
    """Verify TradeWithLimitsRequest schema with limit price."""
    from app.modules.portfolio.schemas import TradeWithLimitsRequest

    req = TradeWithLimitsRequest(
        symbol="AAPL",
        side="buy",
        qty=10,
        limit_price=150.0,
    )
    
    assert req.symbol == "AAPL"
    assert req.side == "buy"
    assert req.qty == 10
    assert req.limit_price == 150.0


def test_trade_with_limits_market_order() -> None:
    """Verify TradeWithLimitsRequest supports market orders (no limit price)."""
    from app.modules.portfolio.schemas import TradeWithLimitsRequest

    req = TradeWithLimitsRequest(
        symbol="MSFT",
        side="sell",
        qty=5,
    )
    
    assert req.symbol == "MSFT"
    assert req.side == "sell"
    assert req.qty == 5
    assert req.limit_price is None, "Market orders should have limit_price=None"


def test_trade_with_status_read_schema() -> None:
    """Verify TradeWithStatusRead response schema exists."""
    from app.modules.portfolio.schemas import TradeWithStatusRead

    # Should be able to import it
    assert TradeWithStatusRead is not None


def test_schema_validation() -> None:
    """Verify schemas properly validate inputs."""
    from app.modules.portfolio.schemas import TradeWithLimitsRequest
    from pydantic import ValidationError
    import pytest

    # Should raise validation error for invalid side
    try:
        TradeWithLimitsRequest(
            symbol="AAPL",
            side="INVALID",
            qty=10,
        )
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass  # Expected


def test_schema_field_types() -> None:
    """Verify schema fields have correct types."""
    from app.modules.portfolio.schemas import TradeWithLimitsRequest

    req = TradeWithLimitsRequest(
        symbol="AAPL",
        side="buy",
        qty=10,
        limit_price=150.0,
    )
    
    assert isinstance(req.symbol, str)
    assert isinstance(req.side, str)
    assert isinstance(req.qty, int)
    assert isinstance(req.limit_price, float) or req.limit_price is None
