from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_password_changed, require_roles
from app.models.user import User
from app.schemas.soc_dashboard import IncidentListResponse
from app.services.incident_service import incident_service
from app.services.wazuh_data_service import wazuh_data

router = APIRouter()
_analyst = require_roles(["Super Admin", "SOC Analyst", "IT Admin"])
_view = require_roles(["Super Admin", "SOC Analyst", "Manager", "Auditor", "IT Admin"])


class AssignBody(BaseModel):
    user_id: str


class StatusBody(BaseModel):
    status: str = Field(pattern="^(open|investigating|contained|resolved|closed)$")


class CommentBody(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


@router.get("", response_model=IncidentListResponse)
async def list_incidents(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _: User = Depends(_view),
    __: User = Depends(require_password_changed),
    db: AsyncSession = Depends(get_db),
) -> IncidentListResponse:
    return await wazuh_data.get_incidents(db, status=status, severity=severity, limit=limit, offset=offset)


@router.post("/{incident_id}/acknowledge")
async def acknowledge_incident(
    incident_id: UUID,
    current_user: User = Depends(_analyst),
    db: AsyncSession = Depends(get_db),
) -> dict:
    inc = await incident_service.acknowledge(db, incident_id, current_user)
    return {"success": True, "status": inc.status}


@router.post("/{incident_id}/assign")
async def assign_incident(
    incident_id: UUID,
    body: AssignBody,
    current_user: User = Depends(_analyst),
    db: AsyncSession = Depends(get_db),
) -> dict:
    inc = await incident_service.assign(db, incident_id, UUID(body.user_id), current_user)
    return {"success": True, "assigned_to": body.user_id, "status": inc.status}


@router.patch("/{incident_id}/status")
async def update_status(
    incident_id: UUID,
    body: StatusBody,
    current_user: User = Depends(_analyst),
    db: AsyncSession = Depends(get_db),
) -> dict:
    inc = await incident_service.update_status(db, incident_id, body.status, current_user)
    return {"success": True, "status": inc.status}


@router.post("/{incident_id}/comments")
async def add_comment(
    incident_id: UUID,
    body: CommentBody,
    current_user: User = Depends(_analyst),
    db: AsyncSession = Depends(get_db),
) -> dict:
    c = await incident_service.add_comment(db, incident_id, current_user, body.body)
    return {"success": True, "comment_id": str(c.id)}


@router.get("/{incident_id}/timeline")
async def incident_timeline(
    incident_id: UUID,
    _: User = Depends(_view),
    db: AsyncSession = Depends(get_db),
) -> dict:
    items = await incident_service.get_timeline(db, incident_id)
    return {
        "timeline": [
            {
                "action": t.action,
                "actor_id": str(t.actor_id) if t.actor_id else None,
                "details": t.details,
                "created_at": t.created_at.isoformat(),
            }
            for t in items
        ]
    }
