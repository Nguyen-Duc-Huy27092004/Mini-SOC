"""SOC correlation: group alerts into incidents."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import WazuhEvent
from app.models.incident import AlertAssignment, Incident, IncidentTimeline

logger = structlog.get_logger()

MITRE_MAP = {
    "authentication": ("Credential Access", "T1110"),
    "network_attack": ("Initial Access", "T1190"),
    "web_application_attack": ("Initial Access", "T1190"),
    "malware": ("Execution", "T1204"),
    "privilege_escalation": ("Privilege Escalation", "T1068"),
    "file_integrity_control": ("Defense Evasion", "T1565"),
    "vulnerability": ("Discovery", "T1082"),
}


class CorrelationEngine:
    BRUTE_FORCE_WINDOW_MIN = 5
    BRUTE_FORCE_THRESHOLD = 20
    SCAN_WINDOW_MIN = 10
    SCAN_THRESHOLD = 50

    async def process_event(self, event: WazuhEvent, db: AsyncSession) -> Optional[Incident]:
        correlation_type, correlation_key = self._detect_pattern(event)
        if not correlation_type:
            return None

        existing = await db.scalar(
            select(Incident).where(
                Incident.correlation_key == correlation_key,
                Incident.status.in_(("open", "investigating")),
            )
        )

        tactic, technique = MITRE_MAP.get(event.category, ("Unknown", "T0000"))

        if existing:
            existing.alert_count += 1
            existing.risk_score = max(existing.risk_score, event.risk_score)
            existing.updated_at = datetime.now(timezone.utc)
            if event.severity == "critical" and existing.severity != "critical":
                existing.severity = "critical"
            db.add(existing)
            await self._link_event(existing.id, event.id, db)
            await self._timeline(db, existing.id, "alert_correlated", {"event_id": str(event.id)})
            await db.commit()
            return existing

        brute = await self._check_brute_force(event, db)
        if brute and correlation_type != "brute_force":
            correlation_type = "brute_force"
            correlation_key = f"brute:{event.source_ip}"

        title = self._title_for(correlation_type, event)
        incident = Incident(
            title=title,
            description=event.rule_description,
            status="open",
            severity=event.severity,
            correlation_key=correlation_key,
            correlation_type=correlation_type,
            source_ip=event.source_ip,
            agent_id=event.agent_id,
            rule_id=event.rule_id,
            category=event.category,
            mitre_tactic=tactic,
            mitre_technique=technique,
            alert_count=1,
            risk_score=event.risk_score,
        )
        db.add(incident)
        await db.flush()
        await self._link_event(incident.id, event.id, db)
        await self._timeline(db, incident.id, "incident_created", {"correlation_type": correlation_type})
        await db.commit()
        await logger.ainfo("incident_created", incident_id=str(incident.id), type=correlation_type)
        return incident

    def _detect_pattern(self, event: WazuhEvent) -> tuple[Optional[str], str]:
        if event.category == "authentication" and event.rule_level >= 8:
            if event.source_ip:
                return "repeated_login", f"auth:{event.source_ip}:{event.agent_id}"
            return "repeated_login", f"auth:{event.agent_id}:{event.rule_id}"

        if event.category in ("network_attack", "web_application_attack") and event.source_ip:
            return "suspicious_scan", f"scan:{event.source_ip}"

        if event.severity in ("critical", "high"):
            return "alert_burst", f"burst:{event.agent_id}:{event.rule_id}:{event.source_ip or 'na'}"

        return None, f"single:{event.event_id}"

    async def _check_brute_force(self, event: WazuhEvent, db: AsyncSession) -> bool:
        if not event.source_ip or event.category != "authentication":
            return False
        since = datetime.now(timezone.utc) - timedelta(minutes=self.BRUTE_FORCE_WINDOW_MIN)
        count = await db.scalar(
            select(func.count(WazuhEvent.id)).where(
                and_(
                    WazuhEvent.source_ip == event.source_ip,
                    WazuhEvent.category == "authentication",
                    WazuhEvent.event_timestamp >= since,
                )
            )
        )
        return (count or 0) >= self.BRUTE_FORCE_THRESHOLD

    def _title_for(self, ctype: str, event: WazuhEvent) -> str:
        labels = {
            "brute_force": f"Tấn công brute-force từ {event.source_ip or 'N/A'}",
            "repeated_login": f"Đăng nhập bất thường — {event.agent_name}",
            "suspicious_scan": f"Quét mạng đáng ngờ — {event.source_ip}",
            "alert_burst": f"Chuỗi cảnh báo — {event.agent_name}",
        }
        return labels.get(ctype, f"Sự cố an ninh — {event.rule_description[:80]}")

    async def _link_event(self, incident_id: UUID, event_id: UUID, db: AsyncSession) -> None:
        exists = await db.scalar(
            select(AlertAssignment.id).where(AlertAssignment.event_id == event_id)
        )
        if not exists:
            db.add(AlertAssignment(incident_id=incident_id, event_id=event_id))

    async def _timeline(
        self, db: AsyncSession, incident_id: UUID, action: str, details: dict | None = None
    ) -> None:
        db.add(
            IncidentTimeline(
                incident_id=incident_id,
                action=action,
                details=details or {},
            )
        )


correlation_engine = CorrelationEngine()
