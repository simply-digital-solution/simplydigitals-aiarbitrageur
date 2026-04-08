"""APScheduler jobs for price fetching and data cleanup.

In production (Lambda), these are triggered by EventBridge rules that invoke the
Lambda with a structured event: { "action": "fetch_intraday" | "fetch_closing" | "purge_intraday" }
matching the same pattern used by the AIConnoisseur migration handler.

In local/dev the APScheduler background scheduler runs inside the process.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.shared.config import get_settings
from app.shared.database import AsyncSessionLocal
from app.shared.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


# ── Job implementations ───────────────────────────────────────────────────────

async def _job_fetch_intraday() -> None:
    from app.modules.prices.service import PriceService
    async with AsyncSessionLocal() as db:
        await PriceService.refresh_all_intraday(db)
        logger.info("job_fetch_intraday_done")


async def _job_fetch_closing() -> None:
    from app.modules.prices.service import PriceService
    async with AsyncSessionLocal() as db:
        await PriceService.refresh_all_closing(db)
        logger.info("job_fetch_closing_done")


async def _job_purge_intraday() -> None:
    from app.modules.prices.service import PriceService
    async with AsyncSessionLocal() as db:
        count = await PriceService.purge_old_intraday(db)
        logger.info("job_purge_intraday_done", purged=count)


async def _job_fetch_intraday_1min() -> None:
    from app.modules.prices.service import PriceService
    async with AsyncSessionLocal() as db:
        await PriceService.refresh_all_intraday_1min(db)
        logger.info("job_fetch_intraday_1min_done")


async def _job_purge_intraday_1min() -> None:
    from app.modules.prices.service import PriceService
    async with AsyncSessionLocal() as db:
        count = await PriceService.purge_old_intraday_1min(db)
        logger.info("job_purge_intraday_1min_done", purged=count)


async def _job_sync_positions() -> None:
    from app.modules.auth.dependencies import DEFAULT_TRADER_ID
    from app.modules.broker.service import AlpacaBrokerService
    from app.modules.portfolio.models import PortfolioPosition
    async with AsyncSessionLocal() as db:
        try:
            broker = AlpacaBrokerService()
            alpaca_positions = broker.get_positions()

            for pos in alpaca_positions:
                from sqlalchemy import select
                result = await db.execute(
                    select(PortfolioPosition).where(
                        PortfolioPosition.user_id == DEFAULT_TRADER_ID,
                        PortfolioPosition.symbol == pos.symbol,
                    )
                )
                db_pos = result.scalar_one_or_none()

                if db_pos:
                    db_pos.qty = pos.qty
                    db_pos.avg_cost = pos.avg_entry_price
                else:
                    db_pos = PortfolioPosition(
                        user_id=DEFAULT_TRADER_ID,
                        symbol=pos.symbol,
                        qty=pos.qty,
                        avg_cost=pos.avg_entry_price,
                    )
                    db.add(db_pos)

            await db.commit()
            logger.info("job_sync_positions_done", position_count=len(alpaca_positions))
        except Exception as exc:
            logger.error("job_sync_positions_failed", error=str(exc))
            await db.rollback()


async def _job_evaluate_triggers() -> None:
    from app.modules.triggers.service import TriggerService
    async with AsyncSessionLocal() as db:
        await TriggerService.evaluate_all(db)
        logger.info("job_evaluate_triggers_done")


async def _job_refresh_open_trades() -> None:
    from app.modules.auth.dependencies import DEFAULT_TRADER_ID
    from app.modules.portfolio.service import PortfolioService
    async with AsyncSessionLocal() as db:
        try:
            svc = PortfolioService(db)
            updated = await svc.refresh_open_trades(DEFAULT_TRADER_ID)
            await db.commit()
            logger.info("job_refresh_open_trades_done", updated=updated)
        except Exception as exc:
            logger.error("job_refresh_open_trades_failed", error=str(exc))
            await db.rollback()


# ── EventBridge-compatible dispatcher ────────────────────────────────────────

ACTIONS: dict[str, Any] = {
    "fetch_intraday":        _job_fetch_intraday,
    "fetch_closing":         _job_fetch_closing,
    "purge_intraday":        _job_purge_intraday,
    "fetch_intraday_1min":   _job_fetch_intraday_1min,
    "purge_intraday_1min":   _job_purge_intraday_1min,
    "sync_positions":        _job_sync_positions,
    "evaluate_triggers":     _job_evaluate_triggers,
    "refresh_open_trades":   _job_refresh_open_trades,
}



async def dispatch_action(action: str) -> None:
    """Called from the Lambda handler for EventBridge-triggered invocations."""
    job = ACTIONS.get(action)
    if not job:
        logger.warning("unknown_scheduler_action", action=action)
        return
    await job()


# ── In-process APScheduler (dev / non-Lambda deployments) ────────────────────

def start_scheduler() -> None:
    """Start APScheduler background scheduler. Call once on app startup."""
    if settings.is_production:
        logger.info("scheduler_skipped_production", reason="EventBridge handles scheduling")
        return

    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        scheduler = BackgroundScheduler()

        def _run(coro_fn: Any) -> None:
            asyncio.run(coro_fn())

        # Every 5 minutes during market hours (UTC)
        scheduler.add_job(_run, "cron", args=[_job_fetch_intraday],
                          minute="*/5", hour="13-21", day_of_week="mon-fri", id="fetch_intraday")

        # Every 1 minute during market hours (1-min bars for intraday trading)
        scheduler.add_job(_run, "cron", args=[_job_fetch_intraday_1min],
                          minute="*", hour="13-21", day_of_week="mon-fri", id="fetch_intraday_1min")

        # Every 30 seconds during market hours (sync positions from Alpaca)
        scheduler.add_job(_run, "interval", args=[_job_sync_positions],
                          seconds=30, id="sync_positions")

        # Daily at 22:00 UTC (after US market close)
        scheduler.add_job(_run, "cron", args=[_job_fetch_closing],
                          hour=22, minute=0, id="fetch_closing")

        # Daily at midnight UTC
        scheduler.add_job(_run, "cron", args=[_job_purge_intraday],
                          hour=0, minute=0, id="purge_intraday")

        # Daily at 00:05 UTC (purge 1-min bars after 5-min bars)
        scheduler.add_job(_run, "cron", args=[_job_purge_intraday_1min],
                          hour=0, minute=5, id="purge_intraday_1min")

        # Every 1 minute (trigger evaluation for price alerts)
        scheduler.add_job(_run, "cron", args=[_job_evaluate_triggers],
                          minute="*", id="evaluate_triggers")

        # Every 30 seconds (poll Alpaca for open trade status updates — expired, filled, etc.)
        scheduler.add_job(_run, "interval", args=[_job_refresh_open_trades],
                          seconds=30, id="refresh_open_trades")

        scheduler.start()
        logger.info("scheduler_started", jobs=len(scheduler.get_jobs()))
    except ImportError:
        logger.warning("apscheduler_not_installed", hint="pip install apscheduler")
