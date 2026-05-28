from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.core.security import require_password_changed, require_roles
from app.models.asset import Asset
from app.models.user import User
from app.schemas.server import ServerCreateRequest, ServerSummaryResponse
from app.services.provider_factory import get_data_provider
from app.utils.audit import log_portal_action

router = APIRouter()
_view = require_roles(["Super Admin", "SOC Analyst", "IT Admin", "Manager", "Auditor"])
_edit = require_roles(["Super Admin", "IT Admin"])


@router.get("", response_model=ServerSummaryResponse)
async def get_servers(
    _: User = Depends(_view),
    __: User = Depends(require_password_changed),
    db: AsyncSession = Depends(get_db),
) -> ServerSummaryResponse:
    return await get_data_provider().get_servers(db)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_server(
    payload: ServerCreateRequest,
    request: Request,
    current_user: User = Depends(_edit),
    db: AsyncSession = Depends(get_db),
) -> dict:
    new_asset = Asset(
        agent_id=payload.agent_id,
        hostname=payload.hostname,
        ip_address=payload.ip_address,
        os_name=payload.os_name,
        os_version=payload.os_version,
        department=payload.department,
        owner=payload.owner,
        criticality=payload.criticality,
        location=payload.location,
        status="active",
    )
    db.add(new_asset)
    await db.commit()
    await log_portal_action(
        db,
        action="asset_created",
        details={"hostname": payload.hostname, "ip_address": payload.ip_address},
        user_id=current_user.id,
        request=request,
    )
    return {"success": True, "detail": f"Đã thêm máy chủ {payload.hostname}", "id": str(new_asset.id)}


@router.delete("/{asset_id}")
async def delete_server(
    asset_id: str,
    request: Request,
    current_user: User = Depends(_edit),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(Asset).where(Asset.id == uuid.UUID(asset_id))
    asset = (await db.execute(stmt)).scalars().first()
    if not asset:
        raise HTTPException(status_code=404, detail="Không tìm thấy máy chủ")
    hostname = asset.hostname
    await db.delete(asset)
    await db.commit()
    await log_portal_action(
        db,
        action="asset_deleted",
        details={"hostname": hostname, "id": asset_id},
        user_id=current_user.id,
        request=request,
    )
    return {"success": True, "detail": f"Đã xóa máy chủ {hostname}"}
