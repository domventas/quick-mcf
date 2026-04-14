"""
Admin routes — /api/v1/admin
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import APIKey
from app.schemas import APIKeyCreate, APIKeyResponse
from app.services.auth import validate_admin, create_api_key

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"], dependencies=[Depends(validate_admin)])

@router.post("/keys", response_model=APIKeyResponse)
async def generate_key(request: APIKeyCreate, db: AsyncSession = Depends(get_db)):
    """Generate a new API key for a client. Requires Master Key."""
    return await create_api_key(client_name=request.client_name, db=db, key=request.key)

@router.get("/keys", response_model=list[APIKeyResponse])
async def list_keys(db: AsyncSession = Depends(get_db)):
    """List all API keys. Requires Master Key."""
    result = await db.execute(select(APIKey))
    return result.scalars().all()

@router.delete("/keys/{key_id}")
async def deactivate_key(key_id: int, db: AsyncSession = Depends(get_db)):
    """Deactivate an API key."""
    stmt = select(APIKey).where(APIKey.id == key_id)
    result = await db.execute(stmt)
    key_obj = result.scalar_one_or_none()
    
    if not key_obj:
        raise HTTPException(status_code=404, detail="Key not found")
        
    key_obj.is_active = 0
    await db.commit()
    return {"message": "Key deactivated", "id": key_id}
