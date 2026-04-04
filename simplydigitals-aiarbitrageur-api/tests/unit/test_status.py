"""Tests for GET /api/v1/status service connectivity endpoint."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient

# ── _check_yfinance unit tests ────────────────────────────────────────────────


def test_check_yfinance_ok() -> None:
    """Returns ok=True when yfinance returns a valid price."""
    from app.modules.status.router import _check_yfinance

    mock_info = MagicMock()
    mock_info.get.side_effect = lambda key, *_: 150.0 if key == "lastPrice" else None

    with patch("app.modules.status.router.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.fast_info = mock_info
        result = _check_yfinance()

    assert result["ok"] is True
    assert "150" in result["detail"]


def test_check_yfinance_no_price_returns_error() -> None:
    """Returns ok=False when price is None."""
    from app.modules.status.router import _check_yfinance

    mock_info = MagicMock()
    mock_info.get.return_value = None

    with patch("app.modules.status.router.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.fast_info = mock_info
        result = _check_yfinance()

    assert result["ok"] is False
    assert "no price" in result["detail"]


def test_check_yfinance_exception_returns_error() -> None:
    """Returns ok=False when yfinance raises an exception."""
    from app.modules.status.router import _check_yfinance

    with patch("app.modules.status.router.yf.Ticker", side_effect=Exception("network timeout")):
        result = _check_yfinance()

    assert result["ok"] is False
    assert "network timeout" in result["detail"]


# ── _check_alpaca unit tests ──────────────────────────────────────────────────


def test_check_alpaca_client_none_returns_error() -> None:
    """Returns ok=False when broker _client is None (package missing / no creds)."""
    from app.modules.status.router import _check_alpaca

    mock_broker = MagicMock()
    mock_broker._client = None

    with patch("app.modules.status.router.AlpacaBrokerService", return_value=mock_broker):
        result = _check_alpaca()

    assert result["ok"] is False
    assert "not initialised" in result["detail"]


def test_check_alpaca_ok() -> None:
    """Returns ok=True and account value when broker responds."""
    from app.modules.broker.service import AccountInfo
    from app.modules.status.router import _check_alpaca

    mock_broker = MagicMock()
    mock_broker._client = MagicMock()
    mock_broker.get_account.return_value = AccountInfo(
        account_value=100_000.0,
        buying_power=50_000.0,
        cash=50_000.0,
        portfolio_value=100_000.0,
    )

    with patch("app.modules.status.router.AlpacaBrokerService", return_value=mock_broker):
        result = _check_alpaca()

    assert result["ok"] is True
    assert "100,000" in result["detail"]


def test_check_alpaca_broker_error_returns_error() -> None:
    """Returns ok=False when AlpacaBrokerServiceError is raised."""
    from app.modules.broker.service import AlpacaBrokerServiceError
    from app.modules.status.router import _check_alpaca

    mock_broker = MagicMock()
    mock_broker._client = MagicMock()
    mock_broker.get_account.side_effect = AlpacaBrokerServiceError("invalid credentials")

    with patch("app.modules.status.router.AlpacaBrokerService", return_value=mock_broker):
        result = _check_alpaca()

    assert result["ok"] is False
    assert "invalid credentials" in result["detail"]


def test_check_alpaca_unexpected_exception() -> None:
    """Returns ok=False for any unexpected exception."""
    from app.modules.status.router import _check_alpaca

    with patch("app.modules.status.router.AlpacaBrokerService", side_effect=RuntimeError("crash")):
        result = _check_alpaca()

    assert result["ok"] is False
    assert "crash" in result["detail"]


# ── API endpoint tests ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_status_endpoint_returns_200(client: AsyncClient, auth_headers: dict) -> None:
    """GET /status always returns 200 regardless of connectivity."""
    with (
        patch("app.modules.status.router._check_yfinance", return_value={"ok": True, "detail": "ok"}),
        patch("app.modules.status.router._check_alpaca", return_value={"ok": False, "detail": "no creds"}),
    ):
        response = await client.get("/api/v1/status")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_status_endpoint_no_auth_required(client: AsyncClient) -> None:
    """GET /status is accessible without authentication."""
    with (
        patch("app.modules.status.router._check_yfinance", return_value={"ok": True, "detail": "ok"}),
        patch("app.modules.status.router._check_alpaca", return_value={"ok": False, "detail": "no creds"}),
    ):
        response = await client.get("/api/v1/status")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_status_response_shape(client: AsyncClient) -> None:
    """Response contains yfinance and alpaca keys each with ok and detail."""
    with (
        patch("app.modules.status.router._check_yfinance", return_value={"ok": True, "detail": "price $150"}),
        patch("app.modules.status.router._check_alpaca", return_value={"ok": False, "detail": "no creds"}),
    ):
        response = await client.get("/api/v1/status")

    data = response.json()
    assert "yfinance" in data
    assert "alpaca" in data
    for key in ("yfinance", "alpaca"):
        assert "ok" in data[key]
        assert "detail" in data[key]


@pytest.mark.asyncio
async def test_status_reflects_yfinance_ok(client: AsyncClient) -> None:
    """yfinance.ok=True is reflected in the response."""
    with (
        patch("app.modules.status.router._check_yfinance", return_value={"ok": True, "detail": "price $255.92"}),
        patch("app.modules.status.router._check_alpaca", return_value={"ok": False, "detail": "no creds"}),
    ):
        response = await client.get("/api/v1/status")

    assert response.json()["yfinance"]["ok"] is True


@pytest.mark.asyncio
async def test_status_reflects_alpaca_ok(client: AsyncClient) -> None:
    """alpaca.ok=True is reflected when broker is reachable."""
    with (
        patch("app.modules.status.router._check_yfinance", return_value={"ok": True, "detail": "ok"}),
        patch("app.modules.status.router._check_alpaca", return_value={"ok": True, "detail": "account value $100,000.00"}),
    ):
        response = await client.get("/api/v1/status")

    assert response.json()["alpaca"]["ok"] is True


@pytest.mark.asyncio
async def test_status_both_down(client: AsyncClient) -> None:
    """Both services failing is correctly reported."""
    with (
        patch("app.modules.status.router._check_yfinance", return_value={"ok": False, "detail": "timeout"}),
        patch("app.modules.status.router._check_alpaca", return_value={"ok": False, "detail": "invalid key"}),
    ):
        response = await client.get("/api/v1/status")

    data = response.json()
    assert response.status_code == 200  # endpoint itself is always up
    assert data["yfinance"]["ok"] is False
    assert data["alpaca"]["ok"] is False
