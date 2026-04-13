"""
FastAPI application — entry point.
"""

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI

from app.config import settings
from app.database import async_session, init_db
from app.routers import fulfillment, inventory, orders

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scheduled jobs
# ---------------------------------------------------------------------------

async def _run_inventory_sync():
    """Wrapper to run inventory sync as a scheduled job."""
    from app.services.inventory import sync_inventory
    async with async_session() as db:
        try:
            result = await sync_inventory(db)
            logger.info(f"Scheduled inventory sync: {result.get('message', '')}")
        except Exception as e:
            logger.error(f"Scheduled inventory sync failed: {e}", exc_info=True)


async def _run_fulfillment_poll():
    """Wrapper to run fulfillment order poll as a scheduled job."""
    from app.services.order_status import poll_fulfillment_orders
    async with async_session() as db:
        try:
            result = await poll_fulfillment_orders(db)
            logger.info(f"Scheduled fulfillment poll: {result.get('message', '')}")
        except Exception as e:
            logger.error(f"Scheduled fulfillment poll failed: {e}", exc_info=True)


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    logger.info("=" * 60)
    logger.info("MCF Backend starting up")
    logger.info(f"  Environment:  {settings.ENVIRONMENT}")
    logger.info(f"  DRY_RUN:      {settings.DRY_RUN}")
    logger.info(f"  Marketplace:  {settings.SP_API_MARKETPLACE_ID}")
    logger.info(f"  Quicklly:     {'ENABLED' if settings.QUICKLLY_PUSH_ENABLED else 'DISABLED'}")
    logger.info("=" * 60)

    if settings.ENVIRONMENT == "production" and not settings.DRY_RUN:
        logger.warning("ATTENTION: PRODUCTION MODE with DRY_RUN=False - REAL Amazon calls will be made!")

    # Create DB tables
    await init_db()
    logger.info("Database initialized")

    # Start scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _run_inventory_sync,
        trigger=IntervalTrigger(hours=settings.INVENTORY_SYNC_INTERVAL_HOURS),
        id="inventory_sync",
        name=f"Inventory Sync (every {settings.INVENTORY_SYNC_INTERVAL_HOURS}h)",
    )
    scheduler.add_job(
        _run_fulfillment_poll,
        trigger=IntervalTrigger(minutes=settings.ORDER_POLL_INTERVAL_MINUTES),
        id="fulfillment_poll",
        name=f"Fulfillment Poll (every {settings.ORDER_POLL_INTERVAL_MINUTES}min)",
    )
    scheduler.start()
    logger.info("Scheduler started")

    yield

    # --- Shutdown ---
    scheduler.shutdown()
    logger.info("MCF Backend shut down")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="MCF Backend",
    description="Amazon Multi-Channel Fulfillment backend — inventory sync, order management, status tracking",
    version="0.1.0",
    lifespan=lifespan,
)

# Register routers
app.include_router(fulfillment.router)
app.include_router(inventory.router)
app.include_router(orders.router)


# ---------------------------------------------------------------------------
# Health / Info
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Health"])
async def health():
    return {
        "status": "ok",
        "environment": settings.ENVIRONMENT,
        "dry_run": settings.DRY_RUN,
        "marketplace_id": settings.SP_API_MARKETPLACE_ID,
        "quicklly_enabled": settings.QUICKLLY_PUSH_ENABLED,
    }


@app.get("/", tags=["Health"])
async def root():
    return {
        "app": "MCF Backend",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }
