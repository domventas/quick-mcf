"""
Fulfillment API routes — /api/v1/fulfillment
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import CreateFulfillmentRequest, FulfillmentPreviewRequest
from app.services import fulfillment as fulfillment_service
from app.models import APIKey
from app.services.auth import validate_api_key
router = APIRouter(
    prefix="/api/v1/fulfillment", 
    tags=["Fulfillment"]
)


@router.post("/orders")
async def create_order(
    request: CreateFulfillmentRequest, 
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(validate_api_key)
):
    """Create MCF fulfillment order. Respects DRY_RUN setting."""
    result = await fulfillment_service.create_fulfillment_order(request, db)
    return result


@router.get("/orders")
async def list_orders(
    status: str | None = None, 
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(validate_api_key)
):
    """List all tracked fulfillment orders. Optional ?status= filter."""
    return await fulfillment_service.list_fulfillment_orders(db, status=status)


@router.get("/orders/{order_id}", include_in_schema=False)
async def get_order(
    order_id: str, 
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(validate_api_key)
):
    """Get details of a specific fulfillment order."""
    result = await fulfillment_service.get_fulfillment_order(order_id, db)
    if not result:
        return {"error": "Order not found", "order_id": order_id}
    return result


@router.delete("/orders/{order_id}", include_in_schema=False)
async def cancel_order(
    order_id: str, 
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(validate_api_key)
):
    """Cancel a fulfillment order (only if in Received/Planning status)."""
    return await fulfillment_service.cancel_fulfillment_order(order_id, db)
