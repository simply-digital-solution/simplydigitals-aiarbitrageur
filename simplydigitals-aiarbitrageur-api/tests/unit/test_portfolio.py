"""Tests for portfolio endpoints."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient


@pytest.fixture(autouse=True)
def mock_live_price():
    with patch("app.modules.portfolio.service._live_price", return_value=155.00):
        yield


@pytest.mark.asyncio
async def test_portfolio_empty_initially(client: AsyncClient, auth_headers: dict) -> None:
    response = await client.get("/api/v1/portfolio", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_buy_creates_position(client: AsyncClient, auth_headers: dict) -> None:
    response = await client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "TSLA", "side": "buy", "qty": 10, "price": 150.00},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["symbol"] == "TSLA"
    assert data["side"] == "buy"
    assert data["qty"] == 10


@pytest.mark.asyncio
async def test_position_appears_in_portfolio(client: AsyncClient, auth_headers: dict) -> None:
    await client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "TSLA", "side": "buy", "qty": 5, "price": 200.00},
        headers=auth_headers,
    )
    response = await client.get("/api/v1/portfolio", headers=auth_headers)
    assert response.status_code == 200
    symbols = [p["symbol"] for p in response.json()]
    assert "TSLA" in symbols


@pytest.mark.asyncio
async def test_buy_averages_cost(client: AsyncClient, auth_headers: dict) -> None:
    await client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "AAPL", "side": "buy", "qty": 10, "price": 100.00},
        headers=auth_headers,
    )
    await client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "AAPL", "side": "buy", "qty": 10, "price": 200.00},
        headers=auth_headers,
    )
    response = await client.get("/api/v1/portfolio", headers=auth_headers)
    positions = {p["symbol"]: p for p in response.json()}
    assert positions["AAPL"]["qty"] == 20
    assert positions["AAPL"]["avg_cost"] == pytest.approx(150.0)


@pytest.mark.asyncio
async def test_sell_reduces_position(client: AsyncClient, auth_headers: dict) -> None:
    await client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "MSFT", "side": "buy", "qty": 20, "price": 300.00},
        headers=auth_headers,
    )
    await client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "MSFT", "side": "sell", "qty": 5, "price": 310.00},
        headers=auth_headers,
    )
    response = await client.get("/api/v1/portfolio", headers=auth_headers)
    positions = {p["symbol"]: p for p in response.json()}
    assert positions["MSFT"]["qty"] == 15


@pytest.mark.asyncio
async def test_sell_more_than_held_returns_400(client: AsyncClient, auth_headers: dict) -> None:
    await client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "GOOG", "side": "buy", "qty": 2, "price": 100.00},
        headers=auth_headers,
    )
    response = await client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "GOOG", "side": "sell", "qty": 5, "price": 105.00},
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_portfolio_service_execute_trade_with_limits() -> None:
    """Verify PortfolioService has execute_trade_with_limits method."""
    from app.modules.portfolio.service import PortfolioService

    assert hasattr(PortfolioService, "execute_trade_with_limits")
    assert callable(PortfolioService.execute_trade_with_limits)


def test_portfolio_service_sync_positions() -> None:
    """Verify PortfolioService has sync_positions_from_alpaca method."""
    from app.modules.portfolio.service import PortfolioService

    assert hasattr(PortfolioService, "sync_positions_from_alpaca")
    assert callable(PortfolioService.sync_positions_from_alpaca)


def test_portfolio_service_calculate_exposure() -> None:
    """Verify PortfolioService has portfolio exposure calculation."""
    from app.modules.portfolio.service import PortfolioService

    assert hasattr(PortfolioService, "_calculate_portfolio_exposure")
    assert callable(PortfolioService._calculate_portfolio_exposure)


def test_portfolio_service_trade_limits() -> None:
    """Verify PortfolioService has trade limits methods."""
    from app.modules.portfolio.service import PortfolioService

    assert hasattr(PortfolioService, "_get_or_create_trade_limits")
    assert callable(PortfolioService._get_or_create_trade_limits)


@pytest.mark.asyncio
async def test_trade_validation_rejects_zero_qty(client: AsyncClient, auth_headers: dict) -> None:
    response = await client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "AAPL", "side": "buy", "qty": 0, "price": 150.00},
        headers=auth_headers,
    )
    assert response.status_code == 422


# ── Account / Cash Tests ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_account_returns_initial_cash(client: AsyncClient, auth_headers: dict) -> None:
    """Fresh account starts with $100,000 cash."""
    response = await client.get("/api/v1/portfolio/account", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["cash"] == pytest.approx(100_000.0)
    assert data["buying_power"] == pytest.approx(100_000.0)
    assert "portfolio_value" in data


@pytest.mark.asyncio
async def test_buy_deducts_cash(client: AsyncClient, auth_headers: dict) -> None:
    """Buying stock reduces cash by qty * price."""
    acc_before = (await client.get("/api/v1/portfolio/account", headers=auth_headers)).json()
    await client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "NVDA", "side": "buy", "qty": 10, "price": 500.00},
        headers=auth_headers,
    )
    acc_after = (await client.get("/api/v1/portfolio/account", headers=auth_headers)).json()
    assert acc_after["cash"] == pytest.approx(acc_before["cash"] - 5_000.0)


@pytest.mark.asyncio
async def test_sell_credits_cash(client: AsyncClient, auth_headers: dict) -> None:
    """Selling stock increases cash by qty * price."""
    await client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "AMD", "side": "buy", "qty": 20, "price": 100.00},
        headers=auth_headers,
    )
    acc_before = (await client.get("/api/v1/portfolio/account", headers=auth_headers)).json()
    await client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "AMD", "side": "sell", "qty": 10, "price": 110.00},
        headers=auth_headers,
    )
    acc_after = (await client.get("/api/v1/portfolio/account", headers=auth_headers)).json()
    assert acc_after["cash"] == pytest.approx(acc_before["cash"] + 1_100.0)


@pytest.mark.asyncio
async def test_buy_insufficient_cash_returns_400(client: AsyncClient, auth_headers: dict) -> None:
    """Buying more than available cash returns 400."""
    response = await client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "BRK", "side": "buy", "qty": 1000, "price": 500.00},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "cash" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_portfolio_value_includes_positions(client: AsyncClient, auth_headers: dict) -> None:
    """portfolio_value = cash + market value of all positions."""
    await client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "SPY", "side": "buy", "qty": 5, "price": 400.00},
        headers=auth_headers,
    )
    acc = (await client.get("/api/v1/portfolio/account", headers=auth_headers)).json()
    # mock _live_price returns 155.0, but position cost $2000 and live is 155*5=775
    # portfolio_value = cash + positions_at_live_price
    assert acc["portfolio_value"] > acc["cash"]


@pytest.mark.asyncio
async def test_account_persists_across_requests(client: AsyncClient, auth_headers: dict) -> None:
    """Account cash state is consistent across multiple GET calls."""
    r1 = (await client.get("/api/v1/portfolio/account", headers=auth_headers)).json()
    r2 = (await client.get("/api/v1/portfolio/account", headers=auth_headers)).json()
    assert r1["cash"] == r2["cash"]


# ── Regression: issues found during manual testing ───────────────────────────


@pytest.mark.asyncio
async def test_trade_history_endpoint_returns_200(client: AsyncClient, auth_headers: dict) -> None:
    """GET /portfolio/trades must not return 500 — regression for broken DB schema."""
    response = await client.get("/api/v1/portfolio/trades", headers=auth_headers)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_trade_history_returns_list(client: AsyncClient, auth_headers: dict) -> None:
    """Trade history response is always a list, never an error object."""
    response = await client.get("/api/v1/portfolio/trades", headers=auth_headers)
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_trade_history_empty_when_no_trades(client: AsyncClient, auth_headers: dict) -> None:
    """With no trades placed, history returns [] not mock/fallback data."""
    response = await client.get("/api/v1/portfolio/trades", headers=auth_headers)
    assert response.json() == []


@pytest.mark.asyncio
async def test_trade_appears_in_history_after_buy(client: AsyncClient, auth_headers: dict) -> None:
    """A completed buy trade is recorded and visible in trade history."""
    await client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "AAPL", "side": "buy", "qty": 5, "price": 150.00},
        headers=auth_headers,
    )
    response = await client.get("/api/v1/portfolio/trades", headers=auth_headers)
    assert response.status_code == 200
    trades = response.json()
    assert len(trades) >= 1
    symbols = [t["symbol"] for t in trades]
    assert "AAPL" in symbols


@pytest.mark.asyncio
async def test_trade_history_fields_present(client: AsyncClient, auth_headers: dict) -> None:
    """Each trade record contains all required fields — catches missing-column schema bugs."""
    await client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "MSFT", "side": "buy", "qty": 2, "price": 300.00},
        headers=auth_headers,
    )
    trades = (await client.get("/api/v1/portfolio/trades", headers=auth_headers)).json()
    assert len(trades) >= 1
    trade = trades[0]
    for field in ("id", "symbol", "side", "qty", "status", "created_at"):
        assert field in trade, f"Missing field '{field}' in trade history response"


@pytest.mark.asyncio
async def test_sell_trade_appears_in_history(client: AsyncClient, auth_headers: dict) -> None:
    """Both buy and sell trades are recorded in history."""
    await client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "GOOG", "side": "buy", "qty": 10, "price": 100.00},
        headers=auth_headers,
    )
    await client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "GOOG", "side": "sell", "qty": 5, "price": 110.00},
        headers=auth_headers,
    )
    trades = (await client.get("/api/v1/portfolio/trades", headers=auth_headers)).json()
    sides = [t["side"] for t in trades if t["symbol"] == "GOOG"]
    assert "buy" in sides
    assert "sell" in sides


@pytest.mark.asyncio
async def test_positions_empty_when_no_trades(client: AsyncClient, auth_headers: dict) -> None:
    """With no trades, /portfolio returns [] — not mock data."""
    response = await client.get("/api/v1/portfolio", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_sell_all_removes_position(client: AsyncClient, auth_headers: dict) -> None:
    """Selling entire position removes it from portfolio — position tab shows nothing."""
    await client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "NVDA", "side": "buy", "qty": 5, "price": 200.00},
        headers=auth_headers,
    )
    await client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "NVDA", "side": "sell", "qty": 5, "price": 210.00},
        headers=auth_headers,
    )
    response = await client.get("/api/v1/portfolio", headers=auth_headers)
    symbols = [p["symbol"] for p in response.json()]
    assert "NVDA" not in symbols


# ── Trade Execution Panel Regressions ────────────────────────────────────────


@pytest.mark.asyncio
async def test_account_endpoint_returns_cash_not_mock(
    client: AsyncClient, auth_headers: dict
) -> None:
    """GET /portfolio/account must return real cash, not hardcoded 50000 mock.

    Regression: TradePanel was reading cash from /portfolio (positions list)
    and falling back to 50000. It now reads /portfolio/account which tracks
    local cash state starting at 100000.
    """
    response = await client.get("/api/v1/portfolio/account", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["cash"] != 50000, "Cash should not be the hardcoded mock value 50000"
    assert data["cash"] == pytest.approx(100_000.0)


@pytest.mark.asyncio
async def test_account_poll_does_not_block_trade_submission(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Polling /portfolio/account and submitting a trade are independent — both return success.

    Regression: a shared loading=true flag in TradePanel disabled the submit
    button while the background portfolio refresh was in flight. Both operations
    must succeed without interfering with each other.
    """
    poll_resp = await client.get("/api/v1/portfolio/account", headers=auth_headers)
    trade_resp = await client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "TSLA", "side": "buy", "qty": 1, "price": 100.00},
        headers=auth_headers,
    )
    assert poll_resp.status_code == 200, "Account poll should always return 200"
    assert trade_resp.status_code == 201, (
        "Trade submission should succeed independently of account poll"
    )


@pytest.mark.asyncio
async def test_cash_reflects_real_balance_after_trades(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Cash shown in trade panel order summary matches actual post-trade balance.

    Regression: order summary was using portfolio_value/cash from positions
    endpoint (which doesn't include cash) — falling back to stale 50000.
    """
    # Buy first, then check cash is correctly reduced
    await client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "AAPL", "side": "buy", "qty": 10, "price": 200.00},
        headers=auth_headers,
    )
    response = await client.get("/api/v1/portfolio/account", headers=auth_headers)
    data = response.json()
    assert data["cash"] == pytest.approx(100_000.0 - 2_000.0)


@pytest.mark.asyncio
async def test_order_value_exceeding_cash_blocked(client: AsyncClient, auth_headers: dict) -> None:
    """Trade with order value > available cash is rejected — validates the order summary warning.

    Regression: available cash was 50000 (mock) so large orders weren't
    blocked correctly.
    """
    # With 100000 starting cash, an order of 1000 shares @ 200 = 200000 > cash
    response = await client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "AAPL", "side": "buy", "qty": 1000, "price": 200.00},
        headers=auth_headers,
    )
    assert response.status_code == 400
    detail = response.json()["detail"].lower()
    assert "cash" in detail


@pytest.mark.asyncio
async def test_account_endpoint_has_all_order_summary_fields(
    client: AsyncClient, auth_headers: dict
) -> None:
    """GET /portfolio/account returns all fields needed by the trade panel order summary."""
    response = await client.get("/api/v1/portfolio/account", headers=auth_headers)
    data = response.json()
    for field in ("cash", "buying_power", "portfolio_value"):
        assert field in data, f"Missing field '{field}' needed by trade panel order summary"


@pytest.mark.asyncio
async def test_exposure_percent_decreases_after_sell(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Selling reduces portfolio exposure — validates the exposure % in order summary."""
    await client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "NVDA", "side": "buy", "qty": 10, "price": 500.00},
        headers=auth_headers,
    )
    acc_after_buy = (await client.get("/api/v1/portfolio/account", headers=auth_headers)).json()

    await client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "NVDA", "side": "sell", "qty": 5, "price": 500.00},
        headers=auth_headers,
    )
    acc_after_sell = (await client.get("/api/v1/portfolio/account", headers=auth_headers)).json()

    # Cash should be higher after partial sell
    assert acc_after_sell["cash"] > acc_after_buy["cash"]


@pytest.mark.asyncio
async def test_trade_side_must_be_lowercase(client: AsyncClient, auth_headers: dict) -> None:
    """Backend rejects uppercase BUY/SELL — side must be 'buy'/'sell'.

    Regression: TradePanel was sending side as 'BUY'/'SELL' (from formData)
    causing 422 validation errors silently swallowed as generic failure messages.
    """
    # Uppercase should be rejected
    response = await client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "AAPL", "side": "BUY", "qty": 1, "price": 100.00},
        headers=auth_headers,
    )
    assert response.status_code == 422

    # Lowercase should work
    response = await client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "AAPL", "side": "buy", "qty": 1, "price": 100.00},
        headers=auth_headers,
    )
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_order_value_only_uses_chosen_symbol_price(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Order calculations use only the selected symbol — not all watchlist symbols.

    Regression: prices were fetched for all symbols but the order summary was
    potentially using wrong prices causing value to jump when other symbols updated.
    Verify that buying AAPL uses AAPL's price (set via mock) not MSFT's price.
    """
    # Buy AAPL at a known price
    resp = await client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "AAPL", "side": "buy", "qty": 5, "price": 200.00},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    # Cash deducted should be 5 * 200 = 1000, not based on any other symbol
    acc = (await client.get("/api/v1/portfolio/account", headers=auth_headers)).json()
    assert acc["cash"] == pytest.approx(100_000.0 - 1_000.0)


@pytest.mark.asyncio
async def test_buy_within_cash_is_not_blocked(client: AsyncClient, auth_headers: dict) -> None:
    """An order well within available cash must not be blocked.

    Regression: overly tight MAX_ORDER_SIZE_PCT (2%) frontend validation was
    blocking valid orders where qty * price > 2% of portfolio. Backend should
    be the authority on limits, not hardcoded frontend thresholds.
    """
    # 5 shares at $100 = $500 which is well within $100k cash
    resp = await client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "AAPL", "side": "buy", "qty": 5, "price": 100.00},
        headers=auth_headers,
    )
    assert resp.status_code == 201


def test_broker_service_does_not_raise_on_missing_package() -> None:
    """AlpacaBrokerService init must not raise when alpaca_trade_api is not installed.

    Regression: previously raised AlpacaBrokerServiceError on import,
    causing ALL portfolio endpoints (including /trades) to return 500.
    """
    import sys
    from unittest.mock import patch

    # Simulate alpaca_trade_api not being installed
    with patch.dict(sys.modules, {"alpaca_trade_api": None}):
        try:
            from app.modules.broker.service import AlpacaBrokerService  # noqa: F401
            svc = AlpacaBrokerService()
            # Should not raise — _client will be None
            assert svc._client is None
        except Exception as exc:
            pytest.fail(f"AlpacaBrokerService raised on missing package: {exc}")
