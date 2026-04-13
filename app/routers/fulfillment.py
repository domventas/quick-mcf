"""
Fulfillment API routes — /api/v1/fulfillment
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import CreateFulfillmentRequest, FulfillmentPreviewRequest
from app.services import fulfillment as fulfillment_service

router = APIRouter(prefix="/api/v1/fulfillment", tags=["Fulfillment"])


@router.post("/preview")
async def preview(request: FulfillmentPreviewRequest):
    """Get fulfillment preview — validates items, address, returns shipping estimates."""
    result = await fulfillment_service.preview_fulfillment(request)
    return result


@router.post("/orders")
async def create_order(request: CreateFulfillmentRequest, db: AsyncSession = Depends(get_db)):
    """Create MCF fulfillment order. Respects DRY_RUN setting."""
    result = await fulfillment_service.create_fulfillment_order(request, db)
    return result


@router.get("/orders")
async def list_orders(status: str | None = None, db: AsyncSession = Depends(get_db)):
    """List all tracked fulfillment orders. Optional ?status= filter."""
    return await fulfillment_service.list_fulfillment_orders(db, status=status)


@router.get("/orders/{order_id}")
async def get_order(order_id: str, db: AsyncSession = Depends(get_db)):
    """Get details of a specific fulfillment order."""
    result = await fulfillment_service.get_fulfillment_order(order_id, db)
    if not result:
        return {"error": "Order not found", "order_id": order_id}
    return result


@router.delete("/orders/{order_id}")
async def cancel_order(order_id: str, db: AsyncSession = Depends(get_db)):
    """Cancel a fulfillment order (only if in Received/Planning status)."""
    return await fulfillment_service.cancel_fulfillment_order(order_id, db)
