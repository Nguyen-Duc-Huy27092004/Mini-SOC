from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_password_changed, require_roles
from app.models.user import User
from app.services.wazuh_data_service import wazuh_data

router = APIRouter()


@router.get("")
async def get_portal_audit_logs(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    action: Optional[str] = Query(None, max_length=64),
    _: User = Depends(require_roles(["Super Admin", "Auditor", "Manager"])),
    __: User = Depends(require_password_changed),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await wazuh_data.get_audit_logs(db, limit=limit, offset=offset)
