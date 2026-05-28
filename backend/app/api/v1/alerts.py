from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_password_changed, require_roles
from app.models.user import User
from app.schemas.soc_dashboard import AlertListResponse
from app.services.wazuh_data_service import wazuh_data

router = APIRouter()


@router.get("", response_model=AlertListResponse)
async def get_alerts(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    severity: Optional[str] = Query(None, pattern="^(critical|high|medium|low)$"),
    agent_id: Optional[str] = Query(None, max_length=64),
    category: Optional[str] = Query(None, max_length=64),
    src_ip: Optional[str] = Query(None, max_length=45),
    query: Optional[str] = Query(None, max_length=200),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    _: User = Depends(require_roles(["Super Admin", "SOC Analyst", "Manager", "Auditor"])),
    __: User = Depends(require_password_changed),
    db: AsyncSession = Depends(get_db),
) -> AlertListResponse:
    start = datetime.fromisoformat(start_time.replace("Z", "+00:00")) if start_time else None
    end = datetime.fromisoformat(end_time.replace("Z", "+00:00")) if end_time else None
    return await wazuh_data.get_alerts(
        db,
        page=page,
        page_size=page_size,
        severity=severity,
        agent_id=agent_id,
        category=category,
        source_ip=src_ip,
        start_time=start,
        end_time=end,
        query=query,
    )
