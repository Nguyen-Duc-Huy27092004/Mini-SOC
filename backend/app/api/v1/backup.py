from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_password_changed, require_roles
from app.models.user import User
from app.services.provider_factory import get_data_provider

router = APIRouter()


@router.get("")
async def get_backup_status(
    _: User = Depends(require_roles(["Super Admin", "IT Admin", "Manager"])),
    __: User = Depends(require_password_changed),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await get_data_provider().get_backup_status(db)
