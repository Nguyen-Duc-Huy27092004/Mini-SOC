"""Legacy BaseDataProvider adapter — delegates to PostgreSQL WazuhDataService."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.alert import AlertQueryParams, AlertSummaryResponse, AlertItem
from app.schemas.dashboard import DashboardOverview, SecurityScore, TimelineItem, TopAttacker
from app.schemas.server import ServerDetail, ServerSummaryResponse, ServiceStatus, NetworkUsage
from app.services.base_provider import BaseDataProvider
from app.services.wazuh_data_service import wazuh_data


class WazuhDataProvider(BaseDataProvider):
    async def get_dashboard_overview(self, db: AsyncSession) -> DashboardOverview:
        s = await wazuh_data.get_summary(db)
        trends = await wazuh_data.get_trends(db)
        sev = await wazuh_data.get_severity_distribution(db)
        top_ips = await wazuh_data.get_top_attack_ips(db, limit=5)
        dist = {b.severity: b.count for b in sev}
        return DashboardOverview(
            data_status=s.data_status,
            security_score=SecurityScore(
                score=s.average_risk_score,
                level="Tốt" if s.average_risk_score >= 75 else "Trung bình",
                last_updated="",
            ),
            total_servers=s.agents_total,
            agents_online=s.agents_online,
            agents_offline=max(s.agents_total - s.agents_online, 0),
            critical_alerts=s.critical_alerts,
            high_alerts=dist.get("high", 0),
            backup_status="N/A",
            endpoint_count=s.agents_total,
            top_attackers=[
                TopAttacker(ip=t.ip, country=t.country or "N/A", count=t.count, attack_type=t.attack_type)
                for t in top_ips
            ],
            attack_timeline=[
                TimelineItem(timestamp=t.hour, count=t.count, severity="medium") for t in trends
            ],
            alert_distribution_severity=dist,
        )

    async def get_servers(self, db: AsyncSession) -> ServerSummaryResponse:
        agents = await wazuh_data.get_agents(db)
        servers = [
            ServerDetail(
                id=a.agent_id,
                hostname=a.agent_name,
                ip_address=a.ip_address or "0.0.0.0",
                os_name=a.os_name or "Linux",
                os_version="",
                uptime=0,
                cpu_usage=0.0,
                ram_usage=min(a.risk_score, 100.0),
                ram_total_gb=16.0,
                disk_usage=0.0,
                disk_total_gb=500.0,
                antivirus_status="active" if a.status == "active" else "unknown",
                patch_status="unknown",
                services=[ServiceStatus(name="wazuh-agent", status="running")],
                network=NetworkUsage(),
                status="active" if a.status == "active" else "offline",
            )
            for a in agents
        ]
        return ServerSummaryResponse(
            servers=servers,
            total_count=len(servers),
            online_count=sum(1 for s in servers if s.status == "active"),
            offline_count=sum(1 for s in servers if s.status != "active"),
            data_status="available",
        )

    async def get_attacks(self, db: AsyncSession, mode: str = "executive") -> dict:
        geo = await wazuh_data.get_geo_distribution(db)
        top_ips = await wazuh_data.get_top_attack_ips(db)
        return {
            "mode": mode,
            "geo_distribution": [{"country": g.country, "count": g.count} for g in geo],
            "top_attackers": [t.model_dump() for t in top_ips],
        }

    async def get_endpoints(self, db: AsyncSession) -> dict:
        agents = await wazuh_data.get_agents(db)
        return {
            "endpoints": [a.model_dump() for a in agents],
            "total_endpoints": len(agents),
            "risk_distribution": {
                "safe": sum(1 for a in agents if a.risk_score < 30),
                "warning": sum(1 for a in agents if 30 <= a.risk_score < 70),
                "critical": sum(1 for a in agents if a.risk_score >= 70),
            },
        }

    async def get_alerts(self, db: AsyncSession, params: AlertQueryParams) -> AlertSummaryResponse:
        from datetime import datetime

        start = datetime.fromisoformat(params.start_time.replace("Z", "+00:00")) if params.start_time else None
        end = datetime.fromisoformat(params.end_time.replace("Z", "+00:00")) if params.end_time else None
        page = (params.offset // params.limit) + 1 if params.limit else 1
        result = await wazuh_data.get_alerts(
            db,
            page=page,
            page_size=params.limit,
            severity=params.severity,
            agent_id=params.agent_id,
            category=params.category,
            source_ip=None,
            start_time=start,
            end_time=end,
            query=params.query,
        )
        items = [
            AlertItem(
                id=a.id,
                timestamp=a.timestamp.isoformat(),
                rule_id=a.rule_id,
                rule_level=10,
                description=a.description,
                agent_id=a.agent_id,
                agent_name=a.agent_name,
                src_ip=a.source_ip,
                country=a.source_country,
                severity=a.severity,
                category=a.category,
                count=1,
                raw_log=None,
                risk_score=a.risk_score,
            )
            for a in result.alerts
        ]
        sev_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for i in items:
            if i.severity in sev_counts:
                sev_counts[i.severity] += 1
        return AlertSummaryResponse(
            alerts=items,
            total=result.total,
            critical_count=sev_counts["critical"],
            high_count=sev_counts["high"],
            medium_count=sev_counts["medium"],
            low_count=sev_counts["low"],
        )

    async def get_backup_status(self, db: AsyncSession) -> dict:
        return {"status": "unavailable", "message": "Tích hợp backup sẽ bổ sung qua agent inventory"}

    async def get_user_monitoring(self, db: AsyncSession) -> dict:
        from sqlalchemy import func, select
        from datetime import datetime, timedelta, timezone
        from app.models.event import WazuhEvent

        since = datetime.now(timezone.utc) - timedelta(hours=24)
        stmt = (
            select(WazuhEvent.source_user, func.count(WazuhEvent.id))
            .where(
                WazuhEvent.event_timestamp >= since,
                WazuhEvent.category == "authentication",
                WazuhEvent.source_user.isnot(None),
            )
            .group_by(WazuhEvent.source_user)
            .order_by(func.count(WazuhEvent.id).desc())
            .limit(20)
        )
        rows = (await db.execute(stmt)).all()
        return {"users": [{"user": r[0], "events": r[1]} for r in rows]}
