"""Tests for API endpoints."""

from __future__ import annotations


def test_portfolio_endpoints_exist() -> None:
    """Verify portfolio router has required endpoints."""
    from app.modules.portfolio.router import router as portfolio_router

    routes = [route.path for route in portfolio_router.routes]

    # Check for trade-with-limits endpoint
    assert any("trade-with-limits" in str(route) for route in routes), \
        "Missing /trade-with-limits endpoint"

    # Check for sync-positions endpoint
    assert any("sync-positions" in str(route) for route in routes), \
        "Missing /sync-positions endpoint"


def test_prices_endpoints_exist() -> None:
    """Verify prices router has intraday-1min endpoint."""
    from app.modules.prices.router import router as prices_router

    routes = [route.path for route in prices_router.routes]

    # Check for intraday-1min endpoint
    assert any("intraday-1min" in str(route) for route in routes), \
        "Missing intraday-1min endpoint"


def test_portfolio_trade_with_limits_endpoint() -> None:
    """Verify POST /portfolio/trade-with-limits endpoint."""
    from app.modules.portfolio.router import router

    # Find the route
    found = False
    for route in router.routes:
        if "trade-with-limits" in route.path and "POST" in (route.methods or set()):
            found = True
            break

    assert found, "POST /portfolio/trade-with-limits endpoint not found"


def test_portfolio_sync_positions_endpoint() -> None:
    """Verify POST /portfolio/sync-positions endpoint."""
    from app.modules.portfolio.router import router

    # Find the route
    found = False
    for route in router.routes:
        if "sync-positions" in route.path and "POST" in (route.methods or set()):
            found = True
            break

    assert found, "POST /portfolio/sync-positions endpoint not found"


def test_prices_intraday_1min_endpoint() -> None:
    """Verify GET /prices/{symbol}/intraday-1min endpoint."""
    from app.modules.prices.router import router

    # Find the route
    found = False
    for route in router.routes:
        if "intraday-1min" in route.path and "GET" in (route.methods or set()):
            found = True
            break

    assert found, "GET /prices/{symbol}/intraday-1min endpoint not found"
