"""Service connectivity status endpoint."""

from __future__ import annotations

import asyncio
from typing import Any

import yfinance as yf
from fastapi import APIRouter

from app.modules.broker.service import AlpacaBrokerService, AlpacaBrokerServiceError

router = APIRouter(prefix="/status", tags=["status"])


def _check_yfinance() -> dict[str, Any]:
    """Probe yfinance with a minimal ticker fetch."""
    try:
        info = yf.Ticker("AAPL").fast_info
        price = info.get("lastPrice") or info.get("regularMarketPrice")
        if price:
            return {"ok": True, "detail": f"last AAPL price ${float(price):.2f}"}
        return {"ok": False, "detail": "no price returned"}
    except Exception as exc:
        return {"ok": False, "detail": str(exc)}


def _check_alpaca() -> dict[str, Any]:
    """Probe Alpaca by initialising the client and calling get_account."""
    try:
        svc = AlpacaBrokerService()
        if svc._client is None:
            return {"ok": False, "detail": "client not initialised (package missing or no creds)"}
        account = svc.get_account()
        return {
            "ok": True,
            "detail": f"account value ${account.account_value:,.2f}",
        }
    except AlpacaBrokerServiceError as exc:
        return {"ok": False, "detail": str(exc)}
    except Exception as exc:
        return {"ok": False, "detail": str(exc)}


@router.get("")
async def get_status() -> dict[str, Any]:
    """Return connectivity status for yfinance and Alpaca broker."""
    loop = asyncio.get_event_loop()
    yf_result, alpaca_result = await asyncio.gather(
        loop.run_in_executor(None, _check_yfinance),
        loop.run_in_executor(None, _check_alpaca),
    )
    return {
        "yfinance": yf_result,
        "alpaca": alpaca_result,
    }
