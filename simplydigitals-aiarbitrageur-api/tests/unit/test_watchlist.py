"""Tests for watchlist endpoints."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.modules.tickers.models import Ticker, WatchlistItem
from app.modules.tickers.service import _get_or_create_ticker_data

MOCK_TICKER_DATA = {
    "symbol": "AAPL",
    "name": "Apple Inc.",
    "exchange": "NASDAQ",
    "currency": "USD",
}


@pytest.fixture(autouse=True)
def mock_yfinance():
    with patch("app.modules.tickers.service._get_or_create_ticker_data", return_value=MOCK_TICKER_DATA):
        yield


@pytest.mark.asyncio
async def test_watchlist_empty_initially(client: AsyncClient, auth_headers: dict) -> None:
    response = await client.get("/api/v1/watchlist", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_add_to_watchlist(client: AsyncClient, auth_headers: dict) -> None:
    response = await client.post("/api/v1/watchlist/AAPL", headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert data["name"] == "Apple Inc."


@pytest.mark.asyncio
async def test_watchlist_shows_added_ticker(client: AsyncClient, auth_headers: dict) -> None:
    await client.post("/api/v1/watchlist/AAPL", headers=auth_headers)
    response = await client.get("/api/v1/watchlist", headers=auth_headers)
    assert response.status_code == 200
    symbols = [item["symbol"] for item in response.json()]
    assert "AAPL" in symbols


@pytest.mark.asyncio
async def test_add_duplicate_returns_409(client: AsyncClient, auth_headers: dict) -> None:
    await client.post("/api/v1/watchlist/AAPL", headers=auth_headers)
    response = await client.post("/api/v1/watchlist/AAPL", headers=auth_headers)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_remove_from_watchlist(client: AsyncClient, auth_headers: dict) -> None:
    await client.post("/api/v1/watchlist/AAPL", headers=auth_headers)
    response = await client.delete("/api/v1/watchlist/AAPL", headers=auth_headers)
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_remove_nonexistent_returns_404(client: AsyncClient, auth_headers: dict) -> None:
    response = await client.delete("/api/v1/watchlist/NONEXISTENT", headers=auth_headers)
    assert response.status_code == 404
