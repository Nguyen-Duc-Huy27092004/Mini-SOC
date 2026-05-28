"""Incident workflow: acknowledge, assign, comment, status."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.incident import Incident, IncidentComment, IncidentTimeline
from app.models.user import User


class IncidentService:
    async def get(self, db: AsyncSession, incident_id: UUID) -> Incident:
        inc = await db.get(Incident, incident_id)
        if not inc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy sự cố")
        return inc

    async def acknowledge(
        self, db: AsyncSession, incident_id: UUID, user: User
    ) -> Incident:
        inc = await self.get(db, incident_id)
        inc.status = "investigating"
        inc.acknowledged_at = datetime.now(timezone.utc)
        inc.acknowledged_by_id = user.id
        db.add(inc)
        await self._timeline(db, incident_id, "acknowledged", user.id)
        await db.commit()
        return inc

    async def assign(
        self, db: AsyncSession, incident_id: UUID, assignee_id: UUID, actor: User
    ) -> Incident:
        inc = await self.get(db, incident_id)
        assignee = await db.get(User, assignee_id)
        if not assignee:
            raise HTTPException(status_code=404, detail="Người dùng không tồn tại")
        inc.assigned_to_id = assignee_id
        inc.status = "investigating"
        db.add(inc)
        await self._timeline(
            db, incident_id, "assigned", actor.id, {"assignee_id": str(assignee_id)}
        )
        await db.commit()
        return inc

    async def update_status(
        self, db: AsyncSession, incident_id: UUID, new_status: str, user: User
    ) -> Incident:
        allowed = {"open", "investigating", "contained", "resolved", "closed"}
        if new_status not in allowed:
            raise HTTPException(status_code=400, detail="Trạng thái không hợp lệ")
        inc = await self.get(db, incident_id)
        inc.status = new_status
        if new_status in ("resolved", "closed"):
            inc.resolved_at = datetime.now(timezone.utc)
        db.add(inc)
        await self._timeline(db, incident_id, f"status_{new_status}", user.id)
        await db.commit()
        return inc

    async def add_comment(
        self, db: AsyncSession, incident_id: UUID, user: User, body: str
    ) -> IncidentComment:
        await self.get(db, incident_id)
        comment = IncidentComment(incident_id=incident_id, user_id=user.id, body=body)
        db.add(comment)
        await self._timeline(db, incident_id, "comment_added", user.id)
        await db.commit()
        await db.refresh(comment)
        return comment

    async def get_timeline(self, db: AsyncSession, incident_id: UUID) -> list:
        await self.get(db, incident_id)
        stmt = (
            select(IncidentTimeline)
            .where(IncidentTimeline.incident_id == incident_id)
            .order_by(IncidentTimeline.created_at)
        )
        return list((await db.execute(stmt)).scalars().all())

    async def _timeline(
        self,
        db: AsyncSession,
        incident_id: UUID,
        action: str,
        actor_id: Optional[UUID],
        details: Optional[dict] = None,
    ) -> None:
        db.add(
            IncidentTimeline(
                incident_id=incident_id,
                action=action,
                actor_id=actor_id,
                details=details or {},
            )
        )


incident_service = IncidentService()
