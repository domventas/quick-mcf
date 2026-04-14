"""
Inventory API routes — /api/v1/inventory
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import inventory as inventory_service
from app.services.auth import validate_api_key

router = APIRouter(
    prefix="/api/v1/inventory", 
    tags=["Inventory"],
    dependencies=[Depends(validate_api_key)]
)


@router.get("")
async def list_inventory(sku: str | None = None, db: AsyncSession = Depends(get_db)):
    """Get current inventory. Optional ?sku= filter."""
    return await inventory_service.get_current_inventory(db, sku=sku)


@router.post("/sync")
async def trigger_sync(db: AsyncSession = Depends(get_db)):
    """Manually trigger an inventory sync (Reports API, 30 mins limit)."""
    result = await inventory_service.sync_inventory(db)
    return result
