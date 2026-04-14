"""
Authentication services for API key validation.
"""

from datetime import datetime
from fastapi import Header, HTTPException, Depends, Security
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import APIKey

from app.config import settings

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def validate_api_key(
    api_key_header: str = Security(api_key_header),
    db: AsyncSession = Depends(get_db)
) -> APIKey:
    """
    Validate the API key provided in the request headers.
    Returns the APIKey object if valid, otherwise raises 401.
    """
    if not api_key_header:
        raise HTTPException(
            status_code=401,
            detail="API Key missing from header (X-API-Key)",
        )

    # Check Master Key
    if settings.MASTER_API_KEY and api_key_header == settings.MASTER_API_KEY:
        # Return a "System" APIKey object (not in DB) or just a mock
        return APIKey(key=api_key_header, client_name="System/Master", is_active=1)

    stmt = select(APIKey).where(APIKey.key == api_key_header, APIKey.is_active == 1)
    result = await db.execute(stmt)
    api_key_obj = result.scalar_one_or_none()

    if not api_key_obj:
        raise HTTPException(
            status_code=401,
            detail="Invalid or inactive API Key",
        )

    # Update last_used_at (optional, but good for tracking)
    api_key_obj.last_used_at = datetime.now()
    await db.commit()

    return api_key_obj

async def validate_admin(
    api_key: APIKey = Depends(validate_api_key)
) -> APIKey:
    """
    Ensure the API key is either the Master Key or has admin privileges.
    For now, only the Master Key (System/Master) is considered admin.
    """
    if api_key.client_name != "System/Master":
        raise HTTPException(
            status_code=403,
            detail="Admin privileges required (Master Key)",
        )
    return api_key

async def create_api_key(client_name: str, db: AsyncSession, key: str | None = None) -> APIKey:
    """Utility to create a new API key."""
    import secrets
    actual_key = key or secrets.token_urlsafe(32)
    new_key = APIKey(
        key=actual_key,
        client_name=client_name,
        is_active=1
    )
    db.add(new_key)
    await db.commit()
    await db.refresh(new_key)
    return new_key
