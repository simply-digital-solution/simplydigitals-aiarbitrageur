"""Tests for ticker search and watchlist endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient

# ── search_tickers unit tests ─────────────────────────────────────────────────


def _mock_search_quotes(quotes: list[dict]) -> MagicMock:
    """Return a mock yf.Search instance with the given quotes."""
    mock = MagicMock()
    mock.quotes = quotes
    return mock


def test_search_returns_symbol_and_name() -> None:
    """search_tickers returns symbol and company name."""
    from app.modules.tickers.service import search_tickers

    mock_quotes = [
        {"symbol": "AAPL", "longname": "Apple Inc.", "exchange": "NMS", "exchDisp": "NASDAQ", "typeDisp": "equity"},
    ]
    with patch("app.modules.tickers.service.yf.Search", return_value=_mock_search_quotes(mock_quotes)):
        results = search_tickers("apple")

    assert len(results) == 1
    assert results[0]["symbol"] == "AAPL"
    assert results[0]["name"] == "Apple Inc."


def test_search_returns_exchange_display() -> None:
    """search_tickers includes human-readable exchange name (exchDisp).

    Regression: previously only returned raw exchange code (e.g. 'NMS')
    instead of display name (e.g. 'NASDAQ').
    """
    from app.modules.tickers.service import search_tickers

    mock_quotes = [
        {"symbol": "MSFT", "longname": "Microsoft Corporation", "exchange": "NMS", "exchDisp": "NASDAQ", "typeDisp": "equity"},
    ]
    with patch("app.modules.tickers.service.yf.Search", return_value=_mock_search_quotes(mock_quotes)):
        results = search_tickers("MSFT")

    assert results[0]["exchange_display"] == "NASDAQ"
    assert results[0]["exchange"] == "NMS"


def test_search_returns_type_display() -> None:
    """search_tickers includes typeDisp (equity, etf, etc.)."""
    from app.modules.tickers.service import search_tickers

    mock_quotes = [
        {"symbol": "SPY", "longname": "SPDR S&P 500 ETF Trust", "exchange": "PCX", "exchDisp": "NYSE Arca", "typeDisp": "etf"},
    ]
    with patch("app.modules.tickers.service.yf.Search", return_value=_mock_search_quotes(mock_quotes)):
        results = search_tickers("SPY")

    assert results[0]["type_display"] == "etf"


def test_search_by_company_name() -> None:
    """search_tickers accepts company name as query (not just ticker symbol)."""
    from app.modules.tickers.service import search_tickers

    mock_quotes = [
        {"symbol": "TSLA", "longname": "Tesla, Inc.", "exchange": "NMS", "exchDisp": "NASDAQ", "typeDisp": "equity"},
        {"symbol": "TM", "longname": "Toyota Motor Corporation", "exchange": "NYQ", "exchDisp": "NYSE", "typeDisp": "equity"},
    ]
    with patch("app.modules.tickers.service.yf.Search", return_value=_mock_search_quotes(mock_quotes)):
        results = search_tickers("tesla")

    symbols = [r["symbol"] for r in results]
    assert "TSLA" in symbols


def test_search_multiple_results() -> None:
    """search_tickers returns all results from yfinance, up to max_results."""
    from app.modules.tickers.service import search_tickers

    mock_quotes = [
        {"symbol": "AAPL", "longname": "Apple Inc.", "exchange": "NMS", "exchDisp": "NASDAQ", "typeDisp": "equity"},
        {"symbol": "APLE", "longname": "Apple Hospitality REIT", "exchange": "NYQ", "exchDisp": "NYSE", "typeDisp": "equity"},
        {"symbol": "APC.DE", "longname": "Apple Inc.", "exchange": "GER", "exchDisp": "XETRA", "typeDisp": "equity"},
    ]
    with patch("app.modules.tickers.service.yf.Search", return_value=_mock_search_quotes(mock_quotes)):
        results = search_tickers("apple")

    assert len(results) == 3


def test_search_skips_entries_without_symbol() -> None:
    """search_tickers filters out results with no symbol field."""
    from app.modules.tickers.service import search_tickers

    mock_quotes = [
        {"symbol": "AAPL", "longname": "Apple Inc.", "exchange": "NMS", "exchDisp": "NASDAQ", "typeDisp": "equity"},
        {"longname": "Mystery Corp"},  # no symbol key
        {"symbol": "", "longname": "Empty symbol"},  # empty symbol
    ]
    with patch("app.modules.tickers.service.yf.Search", return_value=_mock_search_quotes(mock_quotes)):
        results = search_tickers("apple")

    assert all(r["symbol"] for r in results)
    assert len(results) == 1


def test_search_falls_back_to_shortname() -> None:
    """search_tickers uses shortname when longname is absent."""
    from app.modules.tickers.service import search_tickers

    mock_quotes = [
        {"symbol": "XYZ", "shortname": "XYZ Corp", "exchange": "NMS", "exchDisp": "NASDAQ", "typeDisp": "equity"},
    ]
    with patch("app.modules.tickers.service.yf.Search", return_value=_mock_search_quotes(mock_quotes)):
        results = search_tickers("XYZ")

    assert results[0]["name"] == "XYZ Corp"


def test_search_falls_back_to_symbol_when_no_name() -> None:
    """search_tickers uses symbol as name when neither longname nor shortname present."""
    from app.modules.tickers.service import search_tickers

    mock_quotes = [
        {"symbol": "UNKN", "exchange": "NMS", "exchDisp": "NASDAQ", "typeDisp": "equity"},
    ]
    with patch("app.modules.tickers.service.yf.Search", return_value=_mock_search_quotes(mock_quotes)):
        results = search_tickers("UNKN")

    assert results[0]["name"] == "UNKN"


def test_search_returns_empty_on_yfinance_error() -> None:
    """search_tickers returns [] when yfinance raises an exception."""
    from app.modules.tickers.service import search_tickers

    with patch("app.modules.tickers.service.yf.Search", side_effect=Exception("network error")):
        results = search_tickers("anything")

    assert results == []


def test_search_exchange_display_falls_back_to_exchange_code() -> None:
    """exchange_display uses exchange code as fallback when exchDisp is absent."""
    from app.modules.tickers.service import search_tickers

    mock_quotes = [
        {"symbol": "FOO", "longname": "Foo Corp", "exchange": "NYQ", "typeDisp": "equity"},
    ]
    with patch("app.modules.tickers.service.yf.Search", return_value=_mock_search_quotes(mock_quotes)):
        results = search_tickers("FOO")

    assert results[0]["exchange_display"] == "NYQ"


# ── TickerSearchResult schema tests ──────────────────────────────────────────


def test_ticker_search_result_schema_has_exchange_display() -> None:
    """TickerSearchResult schema includes exchange_display and type_display fields."""
    from app.modules.tickers.schemas import TickerSearchResult

    result = TickerSearchResult(
        symbol="AAPL",
        name="Apple Inc.",
        exchange="NMS",
        exchange_display="NASDAQ",
        type_display="equity",
    )
    assert result.exchange_display == "NASDAQ"
    assert result.type_display == "equity"


def test_ticker_search_result_exchange_display_optional() -> None:
    """TickerSearchResult exchange_display and type_display are optional (nullable)."""
    from app.modules.tickers.schemas import TickerSearchResult

    result = TickerSearchResult(symbol="AAPL", name="Apple Inc.")
    assert result.exchange_display is None
    assert result.type_display is None


# ── Ticker search API endpoint tests ─────────────────────────────────────────


def test_ticker_search_endpoint_exists() -> None:
    """GET /tickers/search endpoint is registered."""
    from app.modules.tickers.router import router

    routes = [route.path for route in router.routes]
    assert any("search" in r for r in routes), "Missing /tickers/search endpoint"


def test_ticker_search_endpoint_is_get() -> None:
    """GET /tickers/search uses GET method."""
    from app.modules.tickers.router import router

    for route in router.routes:
        if "search" in route.path:
            assert "GET" in (route.methods or set())
            return
    pytest.fail("/tickers/search route not found")


@pytest.mark.asyncio
async def test_search_endpoint_returns_list(client: AsyncClient, auth_headers: dict) -> None:
    """GET /tickers/search returns a JSON array (not a dict with .tickers key).

    Regression: frontend was calling resp.data.tickers (undefined) instead of
    resp.data because the API returns a plain array, not {tickers: [...]}.
    """
    mock_quotes = [
        {"symbol": "AAPL", "longname": "Apple Inc.", "exchange": "NMS", "exchDisp": "NASDAQ", "typeDisp": "equity"},
    ]
    with patch("app.modules.tickers.service.yf.Search", return_value=_mock_search_quotes(mock_quotes)):
        response = await client.get("/api/v1/tickers/search", params={"q": "apple"}, headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list), f"Expected list, got {type(data).__name__}"


@pytest.mark.asyncio
async def test_search_endpoint_result_fields(client: AsyncClient, auth_headers: dict) -> None:
    """Search results include symbol, name, exchange, exchange_display, type_display."""
    mock_quotes = [
        {"symbol": "MSFT", "longname": "Microsoft Corporation", "exchange": "NMS", "exchDisp": "NASDAQ", "typeDisp": "equity"},
    ]
    with patch("app.modules.tickers.service.yf.Search", return_value=_mock_search_quotes(mock_quotes)):
        response = await client.get("/api/v1/tickers/search", params={"q": "Microsoft"}, headers=auth_headers)

    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    r = results[0]
    assert r["symbol"] == "MSFT"
    assert r["name"] == "Microsoft Corporation"
    assert r["exchange_display"] == "NASDAQ"
    assert r["type_display"] == "equity"


@pytest.mark.asyncio
async def test_search_endpoint_by_company_name(client: AsyncClient, auth_headers: dict) -> None:
    """Search endpoint accepts company names, not just ticker symbols."""
    mock_quotes = [
        {"symbol": "TSLA", "longname": "Tesla, Inc.", "exchange": "NMS", "exchDisp": "NASDAQ", "typeDisp": "equity"},
    ]
    with patch("app.modules.tickers.service.yf.Search", return_value=_mock_search_quotes(mock_quotes)):
        response = await client.get("/api/v1/tickers/search", params={"q": "Tesla"}, headers=auth_headers)

    assert response.status_code == 200
    assert response.json()[0]["symbol"] == "TSLA"


@pytest.mark.asyncio
async def test_search_endpoint_empty_results(client: AsyncClient, auth_headers: dict) -> None:
    """Search with no matches returns an empty list, not an error."""
    with patch("app.modules.tickers.service.yf.Search", return_value=_mock_search_quotes([])):
        response = await client.get("/api/v1/tickers/search", params={"q": "zzznomatch"}, headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_search_endpoint_accessible_without_token(client: AsyncClient) -> None:
    """GET /tickers/search is accessible in single-user mode (no JWT required).

    The app uses a hardcoded default-trader ID and does not enforce token auth.
    Requests without Authorization header still return 200 (not 401/403).
    """
    with patch(
        "app.modules.tickers.service.yf.Search",
        return_value=_mock_search_quotes([]),
    ):
        response = await client.get("/api/v1/tickers/search", params={"q": "AAPL"})
    assert response.status_code == 200


# ── Watchlist API tests ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_watchlist_empty_initially(client: AsyncClient, auth_headers: dict) -> None:
    """Fresh user has an empty watchlist."""
    response = await client.get("/api/v1/watchlist", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_add_to_watchlist(client: AsyncClient, auth_headers: dict) -> None:
    """POST /watchlist/{symbol} adds a ticker and returns 201."""
    mock_info = {
        "longName": "Apple Inc.",
        "exchange": "NMS",
        "currency": "USD",
        "regularMarketPrice": 150.0,
    }
    with patch("app.modules.tickers.service.yf.Ticker") as mock_yf:
        mock_yf.return_value.info = mock_info
        response = await client.post("/api/v1/watchlist/AAPL", headers=auth_headers)

    assert response.status_code == 201
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert data["name"] == "Apple Inc."


@pytest.mark.asyncio
async def test_watchlist_shows_added_ticker(client: AsyncClient, auth_headers: dict) -> None:
    """Ticker added to watchlist appears in GET /watchlist."""
    mock_info = {
        "longName": "Tesla, Inc.",
        "exchange": "NMS",
        "currency": "USD",
        "regularMarketPrice": 200.0,
    }
    with patch("app.modules.tickers.service.yf.Ticker") as mock_yf:
        mock_yf.return_value.info = mock_info
        await client.post("/api/v1/watchlist/TSLA", headers=auth_headers)

    response = await client.get("/api/v1/watchlist", headers=auth_headers)
    symbols = [item["symbol"] for item in response.json()]
    assert "TSLA" in symbols


@pytest.mark.asyncio
async def test_add_duplicate_to_watchlist_returns_409(client: AsyncClient, auth_headers: dict) -> None:
    """Adding the same ticker twice returns 409 Conflict."""
    mock_info = {
        "longName": "Microsoft Corporation",
        "exchange": "NMS",
        "currency": "USD",
        "regularMarketPrice": 300.0,
    }
    with patch("app.modules.tickers.service.yf.Ticker") as mock_yf:
        mock_yf.return_value.info = mock_info
        await client.post("/api/v1/watchlist/MSFT", headers=auth_headers)
        response = await client.post("/api/v1/watchlist/MSFT", headers=auth_headers)

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_remove_from_watchlist(client: AsyncClient, auth_headers: dict) -> None:
    """DELETE /watchlist/{symbol} removes the ticker and returns 204."""
    mock_info = {
        "longName": "Meta Platforms Inc.",
        "exchange": "NMS",
        "currency": "USD",
        "regularMarketPrice": 500.0,
    }
    with patch("app.modules.tickers.service.yf.Ticker") as mock_yf:
        mock_yf.return_value.info = mock_info
        await client.post("/api/v1/watchlist/META", headers=auth_headers)

    response = await client.delete("/api/v1/watchlist/META", headers=auth_headers)
    assert response.status_code == 204

    watchlist = (await client.get("/api/v1/watchlist", headers=auth_headers)).json()
    symbols = [item["symbol"] for item in watchlist]
    assert "META" not in symbols


@pytest.mark.asyncio
async def test_remove_nonexistent_from_watchlist_returns_404(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Removing a ticker not in watchlist returns 404."""
    response = await client.delete("/api/v1/watchlist/ZZZNOTHERE", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_watchlist_item_has_exchange_field(client: AsyncClient, auth_headers: dict) -> None:
    """Watchlist items include exchange field for market display."""
    mock_info = {
        "longName": "Alphabet Inc.",
        "exchange": "NMS",
        "currency": "USD",
        "regularMarketPrice": 130.0,
    }
    with patch("app.modules.tickers.service.yf.Ticker") as mock_yf:
        mock_yf.return_value.info = mock_info
        await client.post("/api/v1/watchlist/GOOGL", headers=auth_headers)

    watchlist = (await client.get("/api/v1/watchlist", headers=auth_headers)).json()
    item = next(i for i in watchlist if i["symbol"] == "GOOGL")
    assert "exchange" in item
    assert item["exchange"] == "NMS"
