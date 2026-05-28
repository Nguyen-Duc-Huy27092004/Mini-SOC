from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

import structlog
from fastapi import Request
from sqlalchemy import cast, String
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import PortalAuditLog

logger = structlog.get_logger()


async def log_portal_action(
    db: AsyncSession,
    action: str,
    details: dict,
    user_id: Optional[UUID] = None,
    request: Optional[Request] = None,
) -> None:
    ip_address = "127.0.0.1"
    user_agent = "System"

    if request and request.client:
        ip_address = request.client.host
        user_agent = request.headers.get("user-agent", "Unknown")

    try:
        audit_log = PortalAuditLog(
            user_id=user_id,
            action=action,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.add(audit_log)
        await db.flush()
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.error("audit_log_failed", error=str(exc))
