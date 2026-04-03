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
    assert callable(getattr(PortfolioService, "execute_trade_with_limits"))


def test_portfolio_service_sync_positions() -> None:
    """Verify PortfolioService has sync_positions_from_alpaca method."""
    from app.modules.portfolio.service import PortfolioService

    assert hasattr(PortfolioService, "sync_positions_from_alpaca")
    assert callable(getattr(PortfolioService, "sync_positions_from_alpaca"))


def test_portfolio_service_calculate_exposure() -> None:
    """Verify PortfolioService has portfolio exposure calculation."""
    from app.modules.portfolio.service import PortfolioService

    assert hasattr(PortfolioService, "_calculate_portfolio_exposure")
    assert callable(getattr(PortfolioService, "_calculate_portfolio_exposure"))


def test_portfolio_service_trade_limits() -> None:
    """Verify PortfolioService has trade limits methods."""
    from app.modules.portfolio.service import PortfolioService

    assert hasattr(PortfolioService, "_get_or_create_trade_limits")
    assert callable(getattr(PortfolioService, "_get_or_create_trade_limits"))


@pytest.mark.asyncio
async def test_trade_validation_rejects_zero_qty(client: AsyncClient, auth_headers: dict) -> None:
    response = await client.post(
        "/api/v1/portfolio/trade",
        json={"symbol": "AAPL", "side": "buy", "qty": 0, "price": 150.00},
        headers=auth_headers,
    )
    assert response.status_code == 422
