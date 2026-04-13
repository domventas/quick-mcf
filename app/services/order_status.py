"""
Order status service — polls fulfillment orders and detects changes.
Uses listAllFulfillmentOrders + getFulfillmentOrder two-phase approach.
"""

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.amazon_client import amazon_client
from app.config import settings
from app.models import FulfillmentOrderRecord, FulfillmentStatusHistory, SyncState

logger = logging.getLogger(__name__)

from app.constants import map_amazon_status

async def poll_fulfillment_orders(db: AsyncSession) -> dict:
    """
    Two-phase polling:
    1) listAllFulfillmentOrders(queryStartDate=checkpoint) — discover
    2) getFulfillmentOrder(id) — for changed orders only, get details and store in DB
    """
    now = datetime.now(timezone.utc)

    # Load checkpoint
    stmt = select(SyncState).where(SyncState.job_name == "fulfillment_poll")
    result = await db.execute(stmt)
    sync_state = result.scalar_one_or_none()

    if sync_state and sync_state.last_checkpoint:
        # 5-minute overlap for safety
        checkpoint = sync_state.last_checkpoint - timedelta(minutes=5)
    else:
        # First run: look back 24 hours
        checkpoint = now - timedelta(hours=24)

    logger.info(f"Polling fulfillment orders since {checkpoint.isoformat()}")

    # Phase 1: Discover updated orders
    orders = amazon_client.list_all_fulfillment_orders(query_start_date=checkpoint)
    logger.info(f"Found {len(orders)} orders updated since checkpoint")

    changed_count = 0
    failed_count = 0

    for order_summary in orders:
        order_id = order_summary.get("sellerFulfillmentOrderId", "")
        amazon_status = order_summary.get("fulfillmentOrderStatus", "")

        if not order_id:
            continue

        # Check against DB
        stmt = select(FulfillmentOrderRecord).where(
            FulfillmentOrderRecord.seller_fulfillment_order_id == order_id
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        # Phase 2: Get full details for changed or new orders
        # Skip if status hasn't changed (Note: user might want to detect shipment status changes too)
        if existing and existing.amazon_status == amazon_status:
            # We still might want to check if shipment_status changed even if amazon_status didn't
            # but usually they change together. For now, let's stick to amazon_status as trigger.
            continue

        logger.info(f"Status change detected: {order_id} — {existing.amazon_status if existing else 'NEW'} → {amazon_status}")
        changed_count += 1

        try:
            detail = amazon_client.get_fulfillment_order(order_id)
        except Exception as e:
            logger.error(f"Failed to get details for {order_id}: {e}")
            failed_count += 1
            continue

        fulfillment_order = detail.get("fulfillmentOrder", {})
        items = detail.get("fulfillmentOrderItems", [])
        shipments = detail.get("fulfillmentShipments", [])
        
        # User requested: extract fulfillmentShipmentStatus
        shipment_status = None
        if shipments:
            # Taking the status of the first shipment as a representative value
            shipment_status = shipments[0].get("fulfillmentShipmentStatus")

        internal_status = map_amazon_status(amazon_status)

        if existing:
            # Update existing record
            existing.previous_status = existing.amazon_status
            existing.amazon_status = amazon_status
            existing.internal_status = internal_status
            existing.shipment_status = shipment_status
            existing.displayable_order_id = fulfillment_order.get("displayableOrderId")
            existing.shipping_speed_category = fulfillment_order.get("shippingSpeedCategory")
            existing.destination_address_json = json.dumps(fulfillment_order.get("destinationAddress", {}))
            existing.items_json = json.dumps(items)
            existing.shipments_json = json.dumps(shipments)
            existing.amazon_last_updated = now
            existing.last_polled_at = now
            existing.status_changed_at = now
        else:
            # New order discovered
            record = FulfillmentOrderRecord(
                seller_fulfillment_order_id=order_id,
                marketplace_id=settings.SP_API_MARKETPLACE_ID,
                amazon_status=amazon_status,
                internal_status=internal_status,
                shipment_status=shipment_status,
                displayable_order_id=fulfillment_order.get("displayableOrderId"),
                shipping_speed_category=fulfillment_order.get("shippingSpeedCategory"),
                destination_address_json=json.dumps(fulfillment_order.get("destinationAddress", {})),
                items_json=json.dumps(items),
                shipments_json=json.dumps(shipments),
                order_created_at=_parse_date(fulfillment_order.get("receivedDate")),
                amazon_last_updated=now,
                last_polled_at=now,
                status_changed_at=now,
            )
            db.add(record)
            existing = record

        # Log status change
        history = FulfillmentStatusHistory(
            seller_fulfillment_order_id=order_id,
            old_status=existing.previous_status if existing else None,
            new_status=amazon_status,
            shipment_status=shipment_status,
            changed_at=now,
            full_response_json=json.dumps(detail),
        )
        db.add(history)

    # Update checkpoint
    if sync_state:
        sync_state.last_checkpoint = now
    else:
        db.add(SyncState(job_name="fulfillment_poll", last_checkpoint=now))

    await db.commit()

    summary = {
        "status": "ok",
        "message": f"Polled {len(orders)} orders, {changed_count} changed",
        "total_polled": len(orders),
        "changed": changed_count,
        "failures": failed_count,
    }
    logger.info(f"Poll complete: {summary}")
    return summary


async def get_order_history(order_id: str, db: AsyncSession) -> list[dict]:
    """Get status change history for an order."""
    stmt = (
        select(FulfillmentStatusHistory)
        .where(FulfillmentStatusHistory.seller_fulfillment_order_id == order_id)
        .order_by(FulfillmentStatusHistory.changed_at)
    )
    result = await db.execute(stmt)
    records = result.scalars().all()
    return [
        {
            "old_status": r.old_status,
            "new_status": r.new_status,
            "shipment_status": r.shipment_status,
            "changed_at": r.changed_at.isoformat() if r.changed_at else None,
        }
        for r in records
    ]


def _parse_date(date_str: str | None) -> datetime | None:
    """Parse an ISO date string, return None if invalid."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
