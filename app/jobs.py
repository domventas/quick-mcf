"""
Background jobs and task wrappers for APScheduler.
"""

import logging
from app.database import async_session

logger = logging.getLogger(__name__)

async def run_inventory_sync():
    """Wrapper to run inventory sync as a scheduled job."""
    from app.services.inventory import sync_inventory
    async with async_session() as db:
        try:
            result = await sync_inventory(db)
            logger.info(f"Scheduled inventory sync: {result.get('message', '')}")
        except Exception as e:
            logger.error(f"Scheduled inventory sync failed: {e}", exc_info=True)


async def run_fulfillment_poll():
    """Wrapper to run fulfillment order poll as a scheduled job."""
    from app.services.order_status import poll_fulfillment_orders
    async with async_session() as db:
        try:
            result = await poll_fulfillment_orders(db)
            logger.info(f"Scheduled fulfillment poll: {result.get('message', '')}")
        except Exception as e:
            logger.error(f"Scheduled fulfillment poll failed: {e}", exc_info=True)
