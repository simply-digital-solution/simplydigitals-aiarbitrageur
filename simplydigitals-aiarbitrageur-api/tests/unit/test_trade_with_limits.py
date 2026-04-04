"""Tests for POST /portfolio/trade-with-limits endpoint.

Covers: local DB exposure calculation, order size / exposure limit checks,
paper trade ledger update, and Alpaca fallback behaviour.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def mock_live_price_150():
    """Mock _live_price to return 150.0 so limit checks are predictable."""
    with patch("app.modules.portfolio.service._live_price", return_value=150.0):
        yield


@pytest.fixture(autouse=True)
def force_paper_trade():
    """Force paper-trade path by setting broker._client = None.

    The conftest mock_alpaca_broker returns a MagicMock whose ._client is also
    a MagicMock (truthy), so the Alpaca code path is taken and submit_order
    always returns order_id='test-order-1'.  Multiple trades in one test then
    hit a UNIQUE constraint on order_id.

    This fixture patches the broker property so ._client is None, ensuring all
    trade-with-limits tests go through the local paper-trade ledger path unless
    a specific test overrides it.
    """
    from app.modules.broker.service import AlpacaBrokerService

    mock_broker = MagicMock(spec=AlpacaBrokerService)
    mock_broker._client = None  # paper-trade path

    with patch("app.modules.portfolio.service.AlpacaBrokerService", return_value=mock_broker):
        yield


# ── Happy path ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_trade_with_limits_buy_succeeds(client: AsyncClient, auth_headers: dict) -> None:
    """POST /portfolio/trade-with-limits returns 201 for a valid buy order."""
    response = await client.post(
        "/api/v1/portfolio/trade-with-limits",
        json={"symbol": "AAPL", "side": "buy", "qty": 1},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert data["side"] == "buy"
    assert data["qty"] == 1.0


@pytest.mark.asyncio
async def test_trade_with_limits_response_fields(client: AsyncClient, auth_headers: dict) -> None:
    """trade-with-limits response includes all required fields."""
    response = await client.post(
        "/api/v1/portfolio/trade-with-limits",
        json={"symbol": "MSFT", "side": "buy", "qty": 1},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    for field in ("id", "symbol", "side", "qty", "status", "execution_price", "created_at"):
        assert field in data, f"Missing field '{field}' in trade-with-limits response"


@pytest.mark.asyncio
async def test_trade_with_limits_paper_trade_status(client: AsyncClient, auth_headers: dict) -> None:
    """Paper trade (Alpaca unavailable) is recorded with status='filled'."""
    response = await client.post(
        "/api/v1/portfolio/trade-with-limits",
        json={"symbol": "TSLA", "side": "buy", "qty": 1},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["status"] == "filled"


@pytest.mark.asyncio
async def test_trade_with_limits_execution_price_set(client: AsyncClient, auth_headers: dict) -> None:
    """execution_price is populated from _live_price, not left null."""
    response = await client.post(
        "/api/v1/portfolio/trade-with-limits",
        json={"symbol": "AAPL", "side": "buy", "qty": 1},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["execution_price"] == pytest.approx(150.0)


@pytest.mark.asyncio
async def test_trade_with_limits_limit_price_order(client: AsyncClient, auth_headers: dict) -> None:
    """Limit price order uses limit_price for execution, not live price."""
    response = await client.post(
        "/api/v1/portfolio/trade-with-limits",
        json={"symbol": "AAPL", "side": "buy", "qty": 1, "limit_price": 145.0},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["limit_price"] == pytest.approx(145.0)


# ── Local ledger update ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_trade_with_limits_deducts_cash(client: AsyncClient, auth_headers: dict) -> None:
    """Successful buy via trade-with-limits deducts cash from local account.

    Regression: old code only called Alpaca and never updated local UserAccount,
    so cash balance was stale after every trade.
    """
    acc_before = (await client.get("/api/v1/portfolio/account", headers=auth_headers)).json()
    await client.post(
        "/api/v1/portfolio/trade-with-limits",
        json={"symbol": "AAPL", "side": "buy", "qty": 2},
        headers=auth_headers,
    )
    acc_after = (await client.get("/api/v1/portfolio/account", headers=auth_headers)).json()
    # 2 shares × $150 = $300 deducted
    assert acc_after["cash"] == pytest.approx(acc_before["cash"] - 300.0)


@pytest.mark.asyncio
async def test_trade_with_limits_creates_position(client: AsyncClient, auth_headers: dict) -> None:
    """Successful buy creates a position in local portfolio."""
    await client.post(
        "/api/v1/portfolio/trade-with-limits",
        json={"symbol": "NVDA", "side": "buy", "qty": 5},
        headers=auth_headers,
    )
    positions = (await client.get("/api/v1/portfolio", headers=auth_headers)).json()
    symbols = [p["symbol"] for p in positions]
    assert "NVDA" in symbols


@pytest.mark.asyncio
async def test_trade_with_limits_sell_credits_cash(client: AsyncClient, auth_headers: dict) -> None:
    """Selling via trade-with-limits credits cash to local account."""
    # Buy first via plain /trade to establish position
    await client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "AMD", "side": "buy", "qty": 10, "price": 150.0},
        headers=auth_headers,
    )
    acc_before = (await client.get("/api/v1/portfolio/account", headers=auth_headers)).json()

    await client.post(
        "/api/v1/portfolio/trade-with-limits",
        json={"symbol": "AMD", "side": "sell", "qty": 5},
        headers=auth_headers,
    )
    acc_after = (await client.get("/api/v1/portfolio/account", headers=auth_headers)).json()
    # 5 shares × $150 = $750 credited
    assert acc_after["cash"] == pytest.approx(acc_before["cash"] + 750.0)


@pytest.mark.asyncio
async def test_trade_with_limits_appears_in_history(client: AsyncClient, auth_headers: dict) -> None:
    """Trades via trade-with-limits appear in GET /portfolio/trades."""
    await client.post(
        "/api/v1/portfolio/trade-with-limits",
        json={"symbol": "SPY", "side": "buy", "qty": 1},
        headers=auth_headers,
    )
    trades = (await client.get("/api/v1/portfolio/trades", headers=auth_headers)).json()
    symbols = [t["symbol"] for t in trades]
    assert "SPY" in symbols


# ── Exposure calculation (local DB, no Alpaca) ────────────────────────────────


@pytest.mark.asyncio
async def test_trade_with_limits_uses_local_exposure(client: AsyncClient, auth_headers: dict) -> None:
    """Exposure calculation uses local DB, not Alpaca API.

    Regression: _calculate_portfolio_exposure called broker.get_account() which
    returned 503 when Alpaca credentials were absent. Now uses UserAccount + positions.
    """
    # This test relies on the server returning 201, not 503
    response = await client.post(
        "/api/v1/portfolio/trade-with-limits",
        json={"symbol": "AAPL", "side": "buy", "qty": 1},
        headers=auth_headers,
    )
    assert response.status_code != 503, (
        "Got 503 — exposure calculation is still calling Alpaca instead of local DB"
    )
    assert response.status_code == 201


# ── Order size limit ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_trade_with_limits_rejects_oversized_order(client: AsyncClient, auth_headers: dict) -> None:
    """Order exceeding max_order_size_pct (default 2%) returns 400.

    Default account: $100k, 2% = $2000 max. At $150/share, 14 shares = $2100 > $2000.
    """
    response = await client.post(
        "/api/v1/portfolio/trade-with-limits",
        json={"symbol": "AAPL", "side": "buy", "qty": 14},
        headers=auth_headers,
    )
    assert response.status_code == 400
    detail = response.json()["detail"].lower()
    assert "order size" in detail or "max" in detail


@pytest.mark.asyncio
async def test_trade_with_limits_allows_order_at_size_boundary(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Order at exactly max_order_size_pct (2% of $100k = $2000 → 13 shares at $150) is allowed."""
    response = await client.post(
        "/api/v1/portfolio/trade-with-limits",
        json={"symbol": "AAPL", "side": "buy", "qty": 13},
        headers=auth_headers,
    )
    assert response.status_code == 201


# ── Position exposure limit ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_trade_with_limits_rejects_when_exposure_exceeded(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Trade that would push total exposure above max_position_exposure_pct returns 400.

    Default: 10% of $100k = $10k max exposure. Fill up to ~$9k first, then
    try one more small-but-over-limit trade.
    """
    # Fill up ~$9750 exposure (13 shares × $150 × 5 = $9750) in 5 trades
    for _ in range(5):
        await client.post(
            "/api/v1/portfolio/trade-with-limits",
            json={"symbol": "AAPL", "side": "buy", "qty": 13},
            headers=auth_headers,
        )

    # Now any buy pushes past 10% limit
    response = await client.post(
        "/api/v1/portfolio/trade-with-limits",
        json={"symbol": "AAPL", "side": "buy", "qty": 2},
        headers=auth_headers,
    )
    assert response.status_code == 400
    detail = response.json()["detail"].lower()
    assert "exposure" in detail


# ── Validation ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_trade_with_limits_rejects_zero_qty(client: AsyncClient, auth_headers: dict) -> None:
    """qty=0 is rejected with 422 Unprocessable Entity."""
    response = await client.post(
        "/api/v1/portfolio/trade-with-limits",
        json={"symbol": "AAPL", "side": "buy", "qty": 0},
        headers=auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_trade_with_limits_rejects_uppercase_side(
    client: AsyncClient, auth_headers: dict
) -> None:
    """side must be 'buy' or 'sell' (lowercase); 'BUY' returns 422."""
    response = await client.post(
        "/api/v1/portfolio/trade-with-limits",
        json={"symbol": "AAPL", "side": "BUY", "qty": 1},
        headers=auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_trade_with_limits_rejects_no_live_price(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Returns 400 when _live_price cannot fetch a price for the symbol."""
    with patch("app.modules.portfolio.service._live_price", return_value=None):
        response = await client.post(
            "/api/v1/portfolio/trade-with-limits",
            json={"symbol": "FAKE", "side": "buy", "qty": 1},
            headers=auth_headers,
        )
    assert response.status_code == 400
    assert "price" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_trade_with_limits_sell_without_position_returns_400(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Selling a symbol not in portfolio returns 400 Insufficient position."""
    response = await client.post(
        "/api/v1/portfolio/trade-with-limits",
        json={"symbol": "ZZZZ", "side": "sell", "qty": 1},
        headers=auth_headers,
    )
    assert response.status_code == 400


# ── Alpaca integration (mocked) ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_trade_with_limits_calls_alpaca_when_client_available(
    client: AsyncClient, auth_headers: dict
) -> None:
    """When Alpaca client is available, submit_order is called and order_id is set."""
    from app.modules.broker.service import AlpacaBrokerService, OrderInfo

    mock_order = OrderInfo(
        order_id="alpaca-order-123",
        symbol="AAPL",
        qty=1.0,
        side="buy",
        limit_price=None,
        status="filled",
        filled_qty=1.0,
        filled_avg_price=148.0,
    )
    mock_broker = MagicMock(spec=AlpacaBrokerService)
    mock_broker._client = MagicMock()  # non-None → Alpaca path taken
    mock_broker.submit_order.return_value = mock_order

    with patch("app.modules.portfolio.service.AlpacaBrokerService", return_value=mock_broker):
        response = await client.post(
            "/api/v1/portfolio/trade-with-limits",
            json={"symbol": "AAPL", "side": "buy", "qty": 1},
            headers=auth_headers,
        )

    assert response.status_code == 201
    data = response.json()
    assert data["order_id"] == "alpaca-order-123"
    assert data["execution_price"] == pytest.approx(148.0)


@pytest.mark.asyncio
async def test_trade_with_limits_alpaca_error_returns_503(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Alpaca submit_order failure returns 503 Service Unavailable."""
    from app.modules.broker.service import AlpacaBrokerService, AlpacaBrokerServiceError

    mock_broker = MagicMock(spec=AlpacaBrokerService)
    mock_broker._client = MagicMock()  # non-None → Alpaca path taken
    mock_broker.submit_order.side_effect = AlpacaBrokerServiceError("API down")

    with patch("app.modules.portfolio.service.AlpacaBrokerService", return_value=mock_broker):
        response = await client.post(
            "/api/v1/portfolio/trade-with-limits",
            json={"symbol": "AAPL", "side": "buy", "qty": 1},
            headers=auth_headers,
        )

    assert response.status_code == 503
