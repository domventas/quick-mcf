"""
Orders / Fulfillment Status routes — /api/v1/orders
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import fulfillment as fulfillment_service
from app.services import order_status as order_status_service

router = APIRouter(prefix="/api/v1/orders", tags=["Orders"])


@router.post("/sync")
async def trigger_poll(db: AsyncSession = Depends(get_db)):
    """Manually trigger fulfillment order status poll."""
    result = await order_status_service.poll_fulfillment_orders(db)
    return result


@router.get("")
async def list_orders(status: str | None = None, db: AsyncSession = Depends(get_db)):
    """List all tracked fulfillment orders."""
    return await fulfillment_service.list_fulfillment_orders(db, status=status)


@router.get("/{order_id}")
async def get_order(order_id: str, db: AsyncSession = Depends(get_db)):
    """Get full details of a fulfillment order."""
    result = await fulfillment_service.get_fulfillment_order(order_id, db)
    if not result:
        return {"error": "Order not found", "order_id": order_id}
    return result


@router.get("/{order_id}/history")
async def get_order_history(order_id: str, db: AsyncSession = Depends(get_db)):
    """Get status change timeline for a fulfillment order."""
    return await order_status_service.get_order_history(order_id, db)


@router.post("/retry-failed-pushes")
async def retry_failed_pushes(db: AsyncSession = Depends(get_db)):
    """Retry all failed Quicklly pushes."""
    result = await order_status_service.retry_failed_pushes(db)
    return result
