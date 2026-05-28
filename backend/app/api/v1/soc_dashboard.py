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
