"""
PostgreSQL-only data layer — single source of truth for SOC portal.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, case, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import PortalAuditLog
from app.models.event import EndpointInventory, WazuhEvent
from app.models.incident import AlertAssignment, Incident
from app.models.user import User
from app.schemas.soc_dashboard import (
    AgentStatus,
    AlertItemOut,
    AlertListResponse,
    DashboardSummary,
    GeoPoint,
    IncidentListResponse,
    IncidentOut,
    MitreItem,
    RankedIp,
    RankedServer,
    SeverityBucket,
    TrendPoint,
)

COUNTRY_COORDS = {
    "CN": (35.0, 105.0),
    "US": (37.0, -95.0),
    "RU": (61.0, 105.0),
    "VN": (16.0, 108.0),
    "KR": (36.0, 128.0),
    "DE": (51.0, 10.0),
}


class WazuhDataService:
    def _today_start(self) -> datetime:
        now = datetime.now(timezone.utc)
        return now.replace(hour=0, minute=0, second=0, microsecond=0)

    async def get_summary(self, db: AsyncSession) -> DashboardSummary:
        today = self._today_start()
        base = and_(WazuhEvent.event_timestamp >= today, WazuhEvent.is_suppressed.is_(False))

        alerts_today = await db.scalar(select(func.count(WazuhEvent.id)).where(base)) or 0
        critical = await db.scalar(
            select(func.count(WazuhEvent.id)).where(base, WazuhEvent.severity == "critical")
        ) or 0

        servers_under_attack = await db.scalar(
            select(func.count(func.distinct(WazuhEvent.agent_id))).where(
                base, WazuhEvent.severity.in_(("critical", "high"))
            )
        ) or 0

        agents_total = await db.scalar(select(func.count(EndpointInventory.id))) or 0
        agents_online = await db.scalar(
            select(func.count(EndpointInventory.id)).where(EndpointInventory.status == "active")
        ) or 0

        attacks_blocked = await db.scalar(
            select(func.count(WazuhEvent.id)).where(
                WazuhEvent.is_suppressed.is_(True),
                WazuhEvent.event_timestamp >= today,
            )
        ) or 0

        avg_risk = await db.scalar(
            select(func.avg(WazuhEvent.risk_score)).where(base)
        )
        avg_risk = round(float(avg_risk or 0.0), 1)

        return DashboardSummary(
            alerts_today=alerts_today,
            critical_alerts=critical,
            servers_under_attack=servers_under_attack,
            agents_online=agents_online,
            agents_total=agents_total,
            attacks_blocked=attacks_blocked,
            average_risk_score=avg_risk,
            data_status="available" if (alerts_today > 0 or agents_total > 0) else "degraded",
        )

    async def get_trends(self, db: AsyncSession, hours: int = 24) -> List[TrendPoint]:
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        hour_bucket = func.date_trunc("hour", WazuhEvent.event_timestamp)
        stmt = (
            select(hour_bucket, func.count(WazuhEvent.id))
            .where(WazuhEvent.event_timestamp >= since, WazuhEvent.is_suppressed.is_(False))
            .group_by(hour_bucket)
            .order_by(hour_bucket)
        )
        rows = (await db.execute(stmt)).all()
        return [
            TrendPoint(hour=r[0].strftime("%H:%M") if r[0] else "", count=r[1])
            for r in rows
        ]

    async def get_severity_distribution(self, db: AsyncSession) -> List[SeverityBucket]:
        today = self._today_start()
        stmt = (
            select(WazuhEvent.severity, func.count(WazuhEvent.id))
            .where(WazuhEvent.event_timestamp >= today, WazuhEvent.is_suppressed.is_(False))
            .group_by(WazuhEvent.severity)
        )
        rows = (await db.execute(stmt)).all()
        order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        buckets = [SeverityBucket(severity=r[0], count=r[1]) for r in rows]
        buckets.sort(key=lambda b: order.get(b.severity, 9))
        return buckets

    async def get_top_attacked_servers(self, db: AsyncSession, limit: int = 10) -> List[RankedServer]:
        today = self._today_start()
        sev_rank = case(
            (WazuhEvent.severity == "critical", 4),
            (WazuhEvent.severity == "high", 3),
            (WazuhEvent.severity == "medium", 2),
            else_=1,
        )
        stmt = (
            select(
                WazuhEvent.agent_id,
                WazuhEvent.agent_name,
                func.count(WazuhEvent.id),
                func.max(sev_rank),
            )
            .where(WazuhEvent.event_timestamp >= today, WazuhEvent.is_suppressed.is_(False))
            .group_by(WazuhEvent.agent_id, WazuhEvent.agent_name)
            .order_by(desc(func.count(WazuhEvent.id)))
            .limit(limit)
        )
        rank_map = {4: "critical", 3: "high", 2: "medium", 1: "low"}
        rows = (await db.execute(stmt)).all()
        return [
            RankedServer(
                agent_id=r[0],
                agent_name=r[1],
                alert_count=r[2],
                max_severity=rank_map.get(int(r[3] or 1), "low"),
            )
            for r in rows
        ]

    async def get_top_attack_ips(self, db: AsyncSession, limit: int = 10) -> List[RankedIp]:
        today = self._today_start()
        stmt = (
            select(
                WazuhEvent.source_ip,
                WazuhEvent.source_country,
                func.count(WazuhEvent.id),
                WazuhEvent.category,
            )
            .where(
                WazuhEvent.event_timestamp >= today,
                WazuhEvent.source_ip.isnot(None),
                WazuhEvent.is_suppressed.is_(False),
            )
            .group_by(WazuhEvent.source_ip, WazuhEvent.source_country, WazuhEvent.category)
            .order_by(desc(func.count(WazuhEvent.id)))
            .limit(limit)
        )
        rows = (await db.execute(stmt)).all()
        return [
            RankedIp(ip=r[0], country=r[1], count=r[2], attack_type=r[3] or "unknown")
            for r in rows
        ]

    async def get_geo_distribution(self, db: AsyncSession) -> List[GeoPoint]:
        today = self._today_start()
        stmt = (
            select(WazuhEvent.source_country, func.count(WazuhEvent.id))
            .where(
                WazuhEvent.event_timestamp >= today,
                WazuhEvent.source_country.isnot(None),
                WazuhEvent.is_suppressed.is_(False),
            )
            .group_by(WazuhEvent.source_country)
            .order_by(desc(func.count(WazuhEvent.id)))
            .limit(20)
        )
        rows = (await db.execute(stmt)).all()
        out = []
        for country, count in rows:
            lat, lon = COUNTRY_COORDS.get(country or "", (None, None))
            out.append(GeoPoint(country=country or "Unknown", count=count, lat=lat, lon=lon))
        return out

    async def get_agents(self, db: AsyncSession) -> List[AgentStatus]:
        stmt = select(EndpointInventory).order_by(desc(EndpointInventory.current_risk_score))
        agents = (await db.execute(stmt)).scalars().all()
        return [
            AgentStatus(
                agent_id=a.agent_id,
                agent_name=a.agent_name,
                status=a.status,
                ip_address=a.ip_address,
                os_name=a.os_name,
                risk_score=a.current_risk_score,
                critical_alerts=a.critical_alert_count,
            )
            for a in agents
        ]

    async def get_mitre_mapping(self, db: AsyncSession) -> List[MitreItem]:
        from app.services.correlation_engine import MITRE_MAP

        today = self._today_start()
        stmt = (
            select(WazuhEvent.category, func.count(WazuhEvent.id))
            .where(WazuhEvent.event_timestamp >= today, WazuhEvent.is_suppressed.is_(False))
            .group_by(WazuhEvent.category)
        )
        rows = (await db.execute(stmt)).all()
        items = []
        for cat, count in rows:
            tactic, technique = MITRE_MAP.get(cat, ("Khác", "T0000"))
            items.append(MitreItem(tactic=tactic, technique=technique, count=count))
        items.sort(key=lambda x: x.count, reverse=True)
        return items

    async def get_alerts(
        self,
        db: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 50,
        severity: Optional[str] = None,
        agent_id: Optional[str] = None,
        category: Optional[str] = None,
        source_ip: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        query: Optional[str] = None,
    ) -> AlertListResponse:
        filters = [WazuhEvent.is_suppressed.is_(False)]
        if severity:
            filters.append(WazuhEvent.severity == severity)
        if agent_id:
            filters.append(WazuhEvent.agent_id == agent_id)
        if category:
            filters.append(WazuhEvent.category == category)
        if source_ip:
            filters.append(WazuhEvent.source_ip == source_ip)
        if start_time:
            filters.append(WazuhEvent.event_timestamp >= start_time)
        if end_time:
            filters.append(WazuhEvent.event_timestamp <= end_time)
        if query:
            like = f"%{query}%"
            filters.append(
                WazuhEvent.rule_description.ilike(like)
                | WazuhEvent.agent_name.ilike(like)
                | WazuhEvent.source_ip.ilike(like)
            )

        total = await db.scalar(select(func.count(WazuhEvent.id)).where(*filters)) or 0
        offset = (page - 1) * page_size
        stmt = (
            select(WazuhEvent)
            .where(*filters)
            .order_by(desc(WazuhEvent.event_timestamp))
            .offset(offset)
            .limit(page_size)
        )
        events = (await db.execute(stmt)).scalars().all()

        event_ids = [e.id for e in events]
        incident_map: dict[UUID, UUID] = {}
        if event_ids:
            assigns = (
                await db.execute(
                    select(AlertAssignment.event_id, AlertAssignment.incident_id).where(
                        AlertAssignment.event_id.in_(event_ids)
                    )
                )
            ).all()
            incident_map = {a[0]: a[1] for a in assigns}

        alerts = [
            AlertItemOut(
                id=str(e.id),
                event_id=e.event_id,
                timestamp=e.event_timestamp,
                severity=e.severity,
                category=e.category,
                description=e.rule_description,
                agent_id=e.agent_id,
                agent_name=e.agent_name,
                source_ip=e.source_ip,
                source_country=e.source_country,
                risk_score=e.risk_score,
                rule_id=e.rule_id,
                incident_id=str(incident_map[e.id]) if e.id in incident_map else None,
            )
            for e in events
        ]
        return AlertListResponse(alerts=alerts, total=total, page=page, page_size=page_size)

    async def get_incidents(
        self,
        db: AsyncSession,
        *,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> IncidentListResponse:
        filters = []
        if status:
            filters.append(Incident.status == status)
        if severity:
            filters.append(Incident.severity == severity)

        total = await db.scalar(select(func.count(Incident.id)).where(*filters)) or 0
        stmt = (
            select(Incident, User.email)
            .outerjoin(User, Incident.assigned_to_id == User.id)
            .where(*filters)
            .order_by(desc(Incident.updated_at))
            .offset(offset)
            .limit(limit)
        )
        rows = (await db.execute(stmt)).all()
        incidents = [
            IncidentOut(
                id=str(inc.id),
                title=inc.title,
                description=inc.description,
                status=inc.status,
                severity=inc.severity,
                correlation_type=inc.correlation_type,
                source_ip=inc.source_ip,
                agent_id=inc.agent_id,
                alert_count=inc.alert_count,
                risk_score=inc.risk_score,
                assigned_to_email=email,
                mitre_tactic=inc.mitre_tactic,
                mitre_technique=inc.mitre_technique,
                created_at=inc.created_at,
                updated_at=inc.updated_at,
            )
            for inc, email in rows
        ]
        return IncidentListResponse(incidents=incidents, total=total)

    async def get_audit_logs(self, db: AsyncSession, limit: int = 50, offset: int = 0) -> dict:
        total = await db.scalar(select(func.count(PortalAuditLog.id))) or 0
        stmt = (
            select(PortalAuditLog, User.email, User.full_name)
            .outerjoin(User, PortalAuditLog.user_id == User.id)
            .order_by(desc(PortalAuditLog.created_at))
            .offset(offset)
            .limit(limit)
        )
        rows = (await db.execute(stmt)).all()
        logs = [
            {
                "id": str(log.id),
                "action": log.action,
                "details": log.details,
                "ip_address": log.ip_address,
                "user_email": email or "Hệ thống",
                "user_fullname": name or "Hệ thống",
                "created_at": log.created_at.isoformat(),
            }
            for log, email, name in rows
        ]
        return {"logs": logs, "total": total}


wazuh_data = WazuhDataService()
