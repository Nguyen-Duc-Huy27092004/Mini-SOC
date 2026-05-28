from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_password_changed, require_roles
from app.models.user import User
from app.services.provider_factory import get_data_provider

router = APIRouter()


@router.get("")
async def get_attacks(
    mode: str = Query("executive", pattern="^(executive|analyst)$"),
    _: User = Depends(require_roles(["Super Admin", "SOC Analyst", "Manager", "Auditor"])),
    __: User = Depends(require_password_changed),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await get_data_provider().get_attacks(db, mode=mode)
