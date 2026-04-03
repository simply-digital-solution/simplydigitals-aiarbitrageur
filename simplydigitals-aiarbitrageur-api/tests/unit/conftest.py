"""Shared pytest fixtures for Arbitrageur API unit tests."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Use in-memory SQLite for tests
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-at-least-32-chars!!")
os.environ.setdefault("ENVIRONMENT", "testing")

from app.main import create_app  # noqa: E402 — env vars must be set first
from app.shared.database import Base, get_db  # noqa: E402

_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
_TestSession = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)


@pytest.fixture(scope="session", autouse=True)
async def create_tables() -> None:
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with _TestSession() as session:
        yield session
        await session.rollback()


@pytest.fixture
def app(db_session: AsyncSession):
    fastapi_app = create_app()

    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    fastapi_app.dependency_overrides[get_db] = _override_db
    return fastapi_app


@pytest.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Generate a valid JWT for user_id = 'test-user-1'."""
    from jose import jwt

    token = jwt.encode(
        {"sub": "test-user-1", "type": "access"},
        "test-secret-key-that-is-at-least-32-chars!!",
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}
