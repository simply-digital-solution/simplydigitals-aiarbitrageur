"""Shared pytest fixtures for Arbitrageur API unit tests."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Use in-memory SQLite for tests
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-at-least-32-chars!!")
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("ALPACA_API_KEY", "test-key")
os.environ.setdefault("ALPACA_SECRET_KEY", "test-secret")

# Create test database engine and session factory (with isolation_level=None for autocommit)
_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    echo=False,
    connect_args={"check_same_thread": False},
)
_TestSession = async_sessionmaker(
    _engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


# Mock logging before importing app code
with patch("app.shared.logging.configure_logging"):
    pass


@pytest.fixture(scope="session", autouse=True)
def mock_structlog_logger() -> None:  # type: ignore[no-untyped-def]
    """Mock structlog to avoid PrintLogger name issues in tests."""
    import structlog

    # Create a mock logger that ignores all calls
    mock_logger = MagicMock()

    def mock_get_logger(name: str = "") -> MagicMock:  # type: ignore[no-untyped-def]
        """Return our mock logger instead of creating real one."""
        return mock_logger

    with patch.object(structlog, "get_logger", side_effect=mock_get_logger):
        yield


@pytest.fixture(scope="session", autouse=True)
async def setup_test_db() -> AsyncGenerator[None, None]:
    """Create tables once at session start, cleanup at session end."""
    from app.modules.portfolio import models as _pom  # noqa: F401
    from app.modules.prices import models as _pm  # noqa: F401

    # Import all models so they're registered with Base
    from app.modules.tickers import models as _tm  # noqa: F401
    from app.modules.triggers import models as _trm  # noqa: F401
    from app.shared.database import Base

    # Create all tables at session start
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    # Clean up at session end
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a fresh test database session for each test."""
    async with _TestSession() as session:
        yield session
        # Rollback any uncommitted transactions
        try:
            await session.rollback()
        except Exception:
            pass


@pytest.fixture
async def app(db_session: AsyncSession) -> AsyncGenerator:  # type: ignore[no-untyped-def]
    """Provide a FastAPI app with overridden dependencies."""
    from app.main import create_app  # noqa: E402
    from app.shared.database import get_db  # noqa: E402

    fastapi_app = create_app()

    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    fastapi_app.dependency_overrides[get_db] = _override_db
    yield fastapi_app
    fastapi_app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def mock_alpaca_broker() -> None:  # type: ignore[name-defined]
    """Mock Alpaca broker service to avoid API calls in tests."""
    from app.modules.broker.service import AccountInfo, OrderInfo

    # Create a mock broker instance without spec to allow all methods
    mock_broker = MagicMock()
    mock_broker.get_account.return_value = AccountInfo(
        account_value=10000.00,
        buying_power=5000.00,
        cash=5000.00,
        portfolio_value=10000.00,
    )
    mock_broker.get_positions.return_value = []
    mock_broker.submit_order.return_value = OrderInfo(
        order_id="test-order-1",
        symbol="TEST",
        qty=10.0,
        side="buy",
        limit_price=None,
        status="filled",
        filled_qty=10.0,
        filled_avg_price=100.0,
    )
    mock_broker.cancel_order.return_value = None

    with patch("app.modules.portfolio.service.AlpacaBrokerService", return_value=mock_broker):
        yield


@pytest.fixture
async def client(app) -> AsyncGenerator:  # type: ignore[no-untyped-def]
    """Provide an async HTTP client for testing."""
    from httpx import ASGITransport, AsyncClient

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
