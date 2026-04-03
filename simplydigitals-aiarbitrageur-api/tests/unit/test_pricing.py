"""Tests for pricing data and 1-minute bars."""

from __future__ import annotations


def test_price_service_1min_methods() -> None:
    """Verify PriceService has 1-minute bar methods."""
    from app.modules.prices.service import PriceService

    methods = [
        "get_intraday_1min",
        "_refresh_intraday_1min",
        "purge_old_intraday_1min",
        "refresh_all_intraday_1min",
    ]

    for method in methods:
        assert hasattr(PriceService, method), f"PriceService missing method: {method}"


def test_intraday_price_1min_model() -> None:
    """Verify IntradayPrice1Min model is configured correctly."""
    from app.modules.prices.models import IntradayPrice1Min

    # Check table name
    assert IntradayPrice1Min.__tablename__ == "intraday_1min_prices"

    # Check columns
    columns = {col.name for col in IntradayPrice1Min.__table__.columns}
    required = {"ticker_id", "ts", "open", "high", "low", "close", "volume"}

    for col in required:
        assert col in columns, f"IntradayPrice1Min missing column: {col}"


def test_intraday_price_existing_models() -> None:
    """Verify existing price models still work."""
    from app.modules.prices.models import ClosingPrice, IntradayPrice

    # These should still exist for backward compatibility
    assert IntradayPrice.__tablename__ == "intraday_prices"
    assert ClosingPrice.__tablename__ == "closing_prices"


def test_price_refresh_methods_exist() -> None:
    """Verify price service has all refresh methods."""
    from app.modules.prices.service import PriceService

    # Check for methods that handle data refresh/purge
    assert callable(getattr(PriceService, "refresh_all_intraday_1min", None))
    assert callable(getattr(PriceService, "purge_old_intraday_1min", None))
