"""Tests for database models and configuration."""

from __future__ import annotations


def test_trade_model_fields() -> None:
    """Verify Trade model has all required fields."""
    from app.modules.portfolio.models import Trade

    trade_fields = Trade.__table__.columns.keys()
    required_fields = [
        "order_id",
        "limit_price",
        "execution_price",
        "status",
        "created_at",
        "executed_at",
    ]
    
    for field in required_fields:
        assert field in trade_fields, f"Trade model missing field: {field}"


def test_trade_limit_model() -> None:
    """Verify TradeLimit model exists with correct fields."""
    from app.modules.portfolio.models import TradeLimit

    limit_fields = TradeLimit.__table__.columns.keys()
    expected = [
        "user_id",
        "max_position_exposure_pct",
        "max_daily_loss_pct",
        "max_order_size_pct",
    ]
    
    for field in expected:
        assert field in limit_fields, f"TradeLimit model missing field: {field}"


def test_intraday_1min_model() -> None:
    """Verify IntradayPrice1Min model is configured."""
    from app.modules.prices.models import IntradayPrice1Min

    assert IntradayPrice1Min.__tablename__ == "intraday_1min_prices"


def test_ticker_intraday_relationship() -> None:
    """Verify Ticker has relationship to IntradayPrice1Min."""
    from app.modules.tickers.models import Ticker

    ticker_relationships = [rel.key for rel in Ticker.__mapper__.relationships]
    assert "intraday_1min_prices" in ticker_relationships


def test_trade_limit_config() -> None:
    """Verify trade limit configuration from settings."""
    from app.shared.config import get_settings

    settings = get_settings()
    limits = {
        "MAX_POSITION_EXPOSURE_PCT": settings.MAX_POSITION_EXPOSURE_PCT,
        "MAX_DAILY_LOSS_PCT": settings.MAX_DAILY_LOSS_PCT,
        "MAX_ORDER_SIZE_PCT": settings.MAX_ORDER_SIZE_PCT,
    }

    for key, val in limits.items():
        assert isinstance(val, float), f"{key} should be float"
        assert val > 0, f"{key} should be > 0"


def test_alpaca_config() -> None:
    """Verify Alpaca broker configuration."""
    from app.shared.config import get_settings

    settings = get_settings()
    assert settings.ALPACA_API_KEY, "ALPACA_API_KEY not set"
    assert settings.ALPACA_SECRET_KEY, "ALPACA_SECRET_KEY not set"
    assert settings.ALPACA_BASE_URL == "https://paper-api.alpaca.markets"
