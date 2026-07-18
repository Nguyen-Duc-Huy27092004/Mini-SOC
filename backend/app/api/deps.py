from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User

__all__ = ["get_db", "get_current_active_user"]


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Compatibility dependency for routers expecting app.api.deps."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled",
        )
    return current_user
