"""
Fulfillment service — MCF order creation, preview, cancel.
"""

import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.amazon_client import amazon_client
from app.config import settings
from app.models import FulfillmentOrderRecord, FulfillmentStatusHistory
from app.schemas import CreateFulfillmentRequest, FulfillmentPreviewRequest

logger = logging.getLogger(__name__)

from app.constants import map_amazon_status


async def preview_fulfillment(request: FulfillmentPreviewRequest) -> dict:
    """Get fulfillment preview — no commitment, just validation + estimates."""
    if not request.items:
        raise HTTPException(status_code=400, detail="At least one item is required for fulfillment preview.")

    marketplace = request.marketplace_id or settings.SP_API_MARKETPLACE_ID

    body = {
        "marketplaceId": marketplace,
        "address": {
            "name": request.address.name,
            "line1": request.address.line1,
            "line2": request.address.line2,
            "line3": request.address.line3,
            "city": request.address.city,
            "stateOrRegion": request.address.state_or_region,
            "postalCode": request.address.postal_code,
            "countryCode": request.address.country_code,
            "phone": request.address.phone,
        },
        "items": [
            {
                "sellerSku": item.seller_sku,
                "quantity": item.quantity,
                "sellerFulfillmentOrderItemId": item.seller_fulfillment_order_item_id or f"item-{i}",
            }
            for i, item in enumerate(request.items)
        ],
        "shippingSpeedCategories": request.shipping_speed_categories,
    }

    try:
        result = amazon_client.get_fulfillment_preview(body)
        return result
    except Exception as e:
        logger.error(f"Amazon Preview Error: {e}")
        raise HTTPException(status_code=400, detail=f"Amazon fulfillment preview failed: {str(e)}")


async def create_fulfillment_order(request: CreateFulfillmentRequest, db: AsyncSession) -> dict:
    """Create an MCF fulfillment order."""
    if not request.items:
        raise HTTPException(status_code=400, detail="At least one item is required to create a fulfillment order.")

    order_id = request.seller_fulfillment_order_id or f"MCF-{uuid.uuid4().hex[:12].upper()}"
    marketplace = request.marketplace_id or settings.SP_API_MARKETPLACE_ID
    now = datetime.now(timezone.utc)

    body = {
        "marketplaceId": marketplace,
        "sellerFulfillmentOrderId": order_id,
        "displayableOrderId": request.displayable_order_id,
        "displayableOrderDate": (request.displayable_order_date or now).isoformat(),
        "displayableOrderComment": request.displayable_order_comment,
        "shippingSpeedCategory": request.shipping_speed_category,
        "fulfillmentAction": "Hold",  # Safety: always start on HOLD
        "destinationAddress": {
            "name": request.destination_address.name,
            "line1": request.destination_address.line1,
            "line2": request.destination_address.line2,
            "line3": request.destination_address.line3,
            "city": request.destination_address.city,
            "stateOrRegion": request.destination_address.state_or_region,
            "postalCode": request.destination_address.postal_code,
            "countryCode": request.destination_address.country_code,
            "phone": request.destination_address.phone,
        },
        "items": [
            {
                "sellerSku": item.seller_sku,
                "quantity": item.quantity,
                "sellerFulfillmentOrderItemId": item.seller_fulfillment_order_item_id or f"item-{i}",
            }
            for i, item in enumerate(request.items)
        ],
    }

    # DRY RUN — log but don't send to Amazon
    if settings.DRY_RUN:
        logger.warning(f"DRY RUN: Would create fulfillment order {order_id}")
        record = FulfillmentOrderRecord(
            seller_fulfillment_order_id=order_id,
            marketplace_id=marketplace,
            amazon_status="DryRun",
            internal_status="dry_run",
            displayable_order_id=request.displayable_order_id,
            shipping_speed_category=request.shipping_speed_category,
            destination_address_json=json.dumps(body["destinationAddress"]),
            items_json=json.dumps(body["items"]),
            order_created_at=now,
            last_polled_at=now,
            request_json=json.dumps(body),
        )
        db.add(record)
        await db.commit()

        return {
            "seller_fulfillment_order_id": order_id,
            "amazon_status": "DryRun",
            "internal_status": "dry_run",
            "dry_run": True,
            "message": "DRY RUN — no Amazon call made. Set DRY_RUN=False to create real orders.",
            "details": body,
        }

    # REAL CALL
    try:
        result = amazon_client.create_fulfillment_order(body)
    except Exception as e:
        logger.error(f"Amazon Creation Error for {order_id}: {e}")
        # Return a meaningful error to the user
        raise HTTPException(
            status_code=400, 
            detail={
                "error": "Amazon fulfillment order creation failed",
                "message": str(e),
                "order_id": order_id
            }
        )

    record = FulfillmentOrderRecord(
        seller_fulfillment_order_id=order_id,
        marketplace_id=marketplace,
        amazon_status="Received",
        internal_status="received",
        displayable_order_id=request.displayable_order_id,
        shipping_speed_category=request.shipping_speed_category,
        destination_address_json=json.dumps(body["destinationAddress"]),
        items_json=json.dumps(body["items"]),
        order_created_at=now,
        last_polled_at=now,
        request_json=json.dumps(body),
        response_json=json.dumps(result) if result else None,
    )
    db.add(record)

    # Log initial status
    history = FulfillmentStatusHistory(
        seller_fulfillment_order_id=order_id,
        old_status=None,
        new_status="Received",
        changed_at=now,
    )
    db.add(history)
    await db.commit()

    return {
        "seller_fulfillment_order_id": order_id,
        "amazon_status": "Received",
        "internal_status": "received",
        "dry_run": False,
        "message": "Fulfillment order created (on HOLD). Call /ship to start fulfillment.",
        "details": result,
    }


async def get_fulfillment_order(order_id: str, db: AsyncSession) -> dict | None:
    """Get order from DB, optionally refresh from Amazon."""
    stmt = select(FulfillmentOrderRecord).where(
        FulfillmentOrderRecord.seller_fulfillment_order_id == order_id
    )
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()

    if not record:
        # Try fetching directly from Amazon
        try:
            data = amazon_client.get_fulfillment_order(order_id)
            return data
        except Exception as e:
            logger.error(f"Order {order_id} not found in DB or Amazon: {e}")
            return None

    return {
        "seller_fulfillment_order_id": record.seller_fulfillment_order_id,
        "amazon_status": record.amazon_status,
        "internal_status": record.internal_status,
        "shipment_status": record.shipment_status,
        "displayable_order_id": record.displayable_order_id,
        "shipping_speed_category": record.shipping_speed_category,
        "order_created_at": record.order_created_at.isoformat() if record.order_created_at else None,
        "status_changed_at": record.status_changed_at.isoformat() if record.status_changed_at else None,
        "last_polled_at": record.last_polled_at.isoformat() if record.last_polled_at else None,
        "destination_address": json.loads(record.destination_address_json) if record.destination_address_json else None,
        "items": json.loads(record.items_json) if record.items_json else None,
        "shipments": json.loads(record.shipments_json) if record.shipments_json else None,
    }


async def cancel_fulfillment_order(order_id: str, db: AsyncSession) -> dict:
    """Cancel a fulfillment order."""
    if settings.DRY_RUN:
        logger.warning(f"DRY RUN: Would cancel fulfillment order {order_id}")
        return {"status": "dry_run", "message": f"DRY RUN — would cancel {order_id}"}

    try:
        result = amazon_client.cancel_fulfillment_order(order_id)
    except Exception as e:
        logger.error(f"Amazon Cancel Error for {order_id}: {e}")
        raise HTTPException(status_code=400, detail=f"Amazon fulfillment cancellation failed: {str(e)}")

    # Update DB
    stmt = select(FulfillmentOrderRecord).where(
        FulfillmentOrderRecord.seller_fulfillment_order_id == order_id
    )
    res = await db.execute(stmt)
    record = res.scalar_one_or_none()
    if record:
        record.previous_status = record.amazon_status
        record.amazon_status = "Cancelled"
        record.internal_status = "cancelled"
        record.status_changed_at = datetime.now(timezone.utc)

        history = FulfillmentStatusHistory(
            seller_fulfillment_order_id=order_id,
            old_status=record.previous_status,
            new_status="Cancelled",
            changed_at=datetime.now(timezone.utc),
        )
        db.add(history)
        await db.commit()

    return {"status": "cancelled", "message": f"Order {order_id} cancelled", "details": result}


async def list_fulfillment_orders(db: AsyncSession, status: str | None = None) -> list[dict]:
    """List orders from DB with optional status filter."""
    stmt = select(FulfillmentOrderRecord).order_by(FulfillmentOrderRecord.id.desc())
    if status:
        stmt = stmt.where(FulfillmentOrderRecord.internal_status == status)

    result = await db.execute(stmt)
    records = result.scalars().all()

    return [
        {
            "seller_fulfillment_order_id": r.seller_fulfillment_order_id,
            "amazon_status": r.amazon_status,
            "internal_status": r.internal_status,
            "shipment_status": r.shipment_status,
            "displayable_order_id": r.displayable_order_id,
            "shipping_speed_category": r.shipping_speed_category,
            "order_created_at": r.order_created_at.isoformat() if r.order_created_at else None,
            "status_changed_at": r.status_changed_at.isoformat() if r.status_changed_at else None,
        }
        for r in records
    ]
