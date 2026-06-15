"""Executive & SOC dashboard APIs — PostgreSQL only."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_password_changed, require_roles
from app.models.user import User
from app.schemas.soc_dashboard import (
    AgentStatus,
    DashboardSummary,
    GeoPoint,
    MitreItem,
    RankedIp,
    RankedServer,
    SeverityBucket,
    TrendPoint,
)
from app.services.wazuh_data_service import wazuh_data

router = APIRouter()
_roles = ["Super Admin", "SOC Analyst", "Manager", "Auditor", "IT Admin"]


@router.get("/summary", response_model=DashboardSummary)
async def dashboard_summary(
    _: User = Depends(require_roles(_roles)),
    __: User = Depends(require_password_changed),
    db: AsyncSession = Depends(get_db),
) -> DashboardSummary:
    return await wazuh_data.get_summary(db)


@router.get("/trends", response_model=list[TrendPoint])
async def dashboard_trends(
    _: User = Depends(require_roles(_roles)),
    __: User = Depends(require_password_changed),
    db: AsyncSession = Depends(get_db),
) -> list[TrendPoint]:
    return await wazuh_data.get_trends(db)


@router.get("/severity", response_model=list[SeverityBucket])
async def dashboard_severity(
    _: User = Depends(require_roles(_roles)),
    __: User = Depends(require_password_changed),
    db: AsyncSession = Depends(get_db),
) -> list[SeverityBucket]:
    return await wazuh_data.get_severity_distribution(db)


@router.get("/top-attacked-servers", response_model=list[RankedServer])
async def top_servers(
    _: User = Depends(require_roles(_roles)),
    __: User = Depends(require_password_changed),
    db: AsyncSession = Depends(get_db),
) -> list[RankedServer]:
    return await wazuh_data.get_top_attacked_servers(db)


@router.get("/top-attack-ips", response_model=list[RankedIp])
async def top_ips(
    _: User = Depends(require_roles(_roles)),
    __: User = Depends(require_password_changed),
    db: AsyncSession = Depends(get_db),
) -> list[RankedIp]:
    return await wazuh_data.get_top_attack_ips(db)


@router.get("/geo", response_model=list[GeoPoint])
async def dashboard_geo(
    _: User = Depends(require_roles(_roles)),
    __: User = Depends(require_password_changed),
    db: AsyncSession = Depends(get_db),
) -> list[GeoPoint]:
    return await wazuh_data.get_geo_distribution(db)


@router.get("/agents", response_model=list[AgentStatus])
async def dashboard_agents(
    _: User = Depends(require_roles(_roles)),
    __: User = Depends(require_password_changed),
    db: AsyncSession = Depends(get_db),
) -> list[AgentStatus]:
    return await wazuh_data.get_agents(db)


@router.get("/mitre", response_model=list[MitreItem])
async def dashboard_mitre(
    _: User = Depends(require_roles(_roles)),
    __: User = Depends(require_password_changed),
    db: AsyncSession = Depends(get_db),
) -> list[MitreItem]:
    return await wazuh_data.get_mitre_mapping(db)


@router.get("/debug")
async def dashboard_debug(
    _: User = Depends(require_roles(_roles)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Live pipeline status for diagnostics.
    Returns DB counts, collector stats, Wazuh API health, and data availability.
    Does NOT require password_changed — usable on first login.
    """
    from datetime import datetime, timezone
    from sqlalchemy import func, select
    from app.models.event import WazuhEvent, EndpointInventory
    from app.collector.service import get_collector
    from app.core.config import settings

    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    # DB counts
    total_events = await db.scalar(select(func.count(WazuhEvent.id))) or 0
    events_today = await db.scalar(
        select(func.count(WazuhEvent.id)).where(WazuhEvent.event_timestamp >= today)
    ) or 0
    total_agents = await db.scalar(select(func.count(EndpointInventory.id))) or 0
    active_agents = await db.scalar(
        select(func.count(EndpointInventory.id)).where(EndpointInventory.status == "active")
    ) or 0

    # Collector stats
    try:
        collector = get_collector()
        collector_stats = collector.get_stats()
    except Exception as e:
        collector_stats = {"error": str(e)}

    # Wazuh API test (quick)
    wazuh_status = "not_tested"
    try:
        from app.integrations.wazuh_client import WazuhAPIClient
        client = WazuhAPIClient(
            base_url=settings.WAZUH_API_URL,
            username=settings.WAZUH_API_USER,
            password=settings.WAZUH_API_PASSWORD.get_secret_value(),
            verify_ssl=settings.WAZUH_VERIFY_SSL,
            timeout=10,
        )
        token = await client._authenticate()
        wazuh_status = "authenticated" if token else "auth_failed"
        await client.close()
    except Exception as e:
        wazuh_status = f"error: {str(e)[:200]}"

    return {
        "pipeline_status": {
            "database": {
                "total_events": total_events,
                "events_today": events_today,
                "total_agents": total_agents,
                "active_agents": active_agents,
                "has_data": total_events > 0,
            },
            "collector": collector_stats,
            "wazuh_api": {
                "url": settings.WAZUH_API_URL,
                "user": settings.WAZUH_API_USER,
                "verify_ssl": settings.WAZUH_VERIFY_SSL,
                "alerts_file": settings.WAZUH_ALERTS_FILE,
                "status": wazuh_status,
            },
        },
        "data_available": total_events > 0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
