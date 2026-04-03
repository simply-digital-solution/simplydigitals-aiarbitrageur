"""AI Arbitrageur API — FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.shared.config import get_settings
from app.shared.database import engine, Base
from app.shared.logging import configure_logging, get_logger
from app.shared.scheduler import dispatch_action, start_scheduler

settings = get_settings()
configure_logging()
logger = get_logger(__name__)


def _import_all_models() -> None:
    """Force-import all ORM modules so Alembic can discover metadata."""
    from app.modules.tickers import models as _tm  # noqa: F401
    from app.modules.prices import models as _pm   # noqa: F401
    from app.modules.portfolio import models as _pom  # noqa: F401
    from app.modules.triggers import models as _trm  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    _import_all_models()
    if not settings.is_production:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    start_scheduler()
    logger.info("arbitrageur_api_started", env=settings.ENVIRONMENT)
    yield
    await engine.dispose()
    logger.info("arbitrageur_api_stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    # Rate limiting
    limiter = Limiter(key_func=get_remote_address, default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"])
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if not settings.is_production else ["https://simplydigitalsolutions.com.au"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Security headers
    @app.middleware("http")
    async def security_headers(request: Request, call_next):  # type: ignore[type-arg]
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    # Routers
    from app.modules.tickers.router import router as tickers_router, watchlist_router
    from app.modules.prices.router import router as prices_router
    from app.modules.portfolio.router import router as portfolio_router
    from app.modules.triggers.router import router as triggers_router

    prefix = "/api/v1"
    app.include_router(tickers_router, prefix=prefix)
    app.include_router(watchlist_router, prefix=prefix)
    app.include_router(prices_router, prefix=prefix)
    app.include_router(portfolio_router, prefix=prefix)
    app.include_router(triggers_router, prefix=prefix)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}

    return app


app = create_app()


# ── Lambda handler ────────────────────────────────────────────────────────────

async def _handle_scheduled_event(event: dict[str, Any]) -> dict[str, Any]:
    action = event.get("action", "")
    logger.info("lambda_scheduled_event", action=action)
    await dispatch_action(action)
    return {"statusCode": 200, "body": f"action={action} complete"}


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda entry point — handles both HTTP (API Gateway) and EventBridge events."""
    if "action" in event:
        import asyncio
        return asyncio.run(_handle_scheduled_event(event))

    mangum_handler = Mangum(app, lifespan="off")
    return mangum_handler(event, context)
