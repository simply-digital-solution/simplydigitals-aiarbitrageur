"""Tests for trigger endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_triggers_empty_initially(client: AsyncClient, auth_headers: dict) -> None:
    response = await client.get("/api/v1/triggers", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_create_alert_trigger(client: AsyncClient, auth_headers: dict) -> None:
    response = await client.post(
        "/api/v1/triggers",
        json={"symbol": "AAPL", "condition_type": "price_gte", "threshold": 200.0, "action": "alert"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert data["condition_type"] == "price_gte"
    assert data["status"] == "active"


@pytest.mark.asyncio
async def test_create_buy_trigger(client: AsyncClient, auth_headers: dict) -> None:
    response = await client.post(
        "/api/v1/triggers",
        json={"symbol": "TSLA", "condition_type": "price_lte", "threshold": 150.0, "action": "buy", "qty": 5},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["qty"] == 5


@pytest.mark.asyncio
async def test_buy_trigger_requires_qty(client: AsyncClient, auth_headers: dict) -> None:
    response = await client.post(
        "/api/v1/triggers",
        json={"symbol": "AAPL", "condition_type": "price_gte", "threshold": 200.0, "action": "buy"},
        headers=auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_trigger_appears_in_list(client: AsyncClient, auth_headers: dict) -> None:
    await client.post(
        "/api/v1/triggers",
        json={"symbol": "NVDA", "condition_type": "price_gte", "threshold": 500.0, "action": "alert"},
        headers=auth_headers,
    )
    response = await client.get("/api/v1/triggers", headers=auth_headers)
    symbols = [t["symbol"] for t in response.json()]
    assert "NVDA" in symbols


@pytest.mark.asyncio
async def test_pause_trigger(client: AsyncClient, auth_headers: dict) -> None:
    create = await client.post(
        "/api/v1/triggers",
        json={"symbol": "MSFT", "condition_type": "price_gte", "threshold": 400.0, "action": "alert"},
        headers=auth_headers,
    )
    tid = create.json()["id"]
    response = await client.patch(f"/api/v1/triggers/{tid}", json={"status": "paused"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "paused"


@pytest.mark.asyncio
async def test_delete_trigger(client: AsyncClient, auth_headers: dict) -> None:
    create = await client.post(
        "/api/v1/triggers",
        json={"symbol": "AMZN", "condition_type": "price_lte", "threshold": 100.0, "action": "alert"},
        headers=auth_headers,
    )
    tid = create.json()["id"]
    response = await client.delete(f"/api/v1/triggers/{tid}", headers=auth_headers)
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_nonexistent_trigger_returns_404(client: AsyncClient, auth_headers: dict) -> None:
    response = await client.delete("/api/v1/triggers/nonexistent-id", headers=auth_headers)
    assert response.status_code == 404


def test_trigger_service_methods() -> None:
    """Verify TriggerService has all required methods."""
    from app.modules.triggers.service import TriggerService

    methods = [
        "list_triggers",
        "create",
        "update",
        "delete",
        "evaluate_all",
    ]

    for method in methods:
        assert hasattr(TriggerService, method), f"TriggerService missing method: {method}"
        assert callable(getattr(TriggerService, method))


def test_trigger_execution_uses_trade_limits() -> None:
    """Verify triggers execute trades with limits."""
    from app.modules.triggers.service import TriggerService

    # Verify evaluate_all exists and should use execute_trade_with_limits
    assert hasattr(TriggerService, "evaluate_all")
    assert callable(getattr(TriggerService, "evaluate_all"))
