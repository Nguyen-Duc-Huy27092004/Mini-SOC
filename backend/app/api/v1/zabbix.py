"""
Zabbix API Routes — /api/v1/zabbix/*

All 19 endpoints:
  GET  /overview          — infrastructure overview KPI cards
  GET  /summary           — host + problem counts + health score
  GET  /hosts             — list of all monitored hosts
  GET  /problems          — active problems with severity
  GET  /triggers          — trigger states
  GET  /events            — recent events (24h)
  GET  /severity          — severity distribution
  GET  /top-hosts         — top problem hosts (ranked)
  GET  /top-servers       — top 10 servers by CPU/RAM/Disk
  GET  /resource-usage    — CPU / Memory / Disk per host
  GET  /resources         — alias for resource-usage
  GET  /availability      — per-host availability status
  GET  /timeline          — hourly problem timeline
  GET  /charts            — all chart data bundled
  GET  /assets            — asset inventory list
  POST /assets            — create asset
  PUT  /assets/{id}       — update asset
  DELETE /assets/{id}     — delete asset
  GET  /maintenance       — maintenance schedule
  POST /maintenance       — create maintenance entry
  PUT  /maintenance/{id}  — update maintenance entry
  DELETE /maintenance/{id} — delete maintenance entry
  GET  /tasks             — task recommendations
  PUT  /tasks/{id}        — update task status
  GET  /notifications     — notification log
  POST /notifications/test — send test email

Auth: same pattern as Wazuh routes (require_roles + require_password_changed).
Graceful fallback: when Zabbix is offline, returns empty data rather than 500.
"""
from __future__ import annotations

from typing import Any, Dict, List

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import require_password_changed, require_roles
from app.models.user import User
from app.schemas.zabbix import (
    ZabbixAssetCreate,
    ZabbixAssetOut,
    ZabbixAssetUpdate,
    ZabbixAvailabilitySummary,
    ZabbixChartsResponse,
    ZabbixHostOut,
    ZabbixMaintenanceCreate,
    ZabbixMaintenanceOut,
    ZabbixMaintenanceUpdate,
    ZabbixNotificationOut,
    ZabbixNotificationTestRequest,
    ZabbixOverviewResponse,
    ZabbixProblemOut,
    ZabbixResourceUsage,
    ZabbixSeverityDistribution,
    ZabbixSummaryResponse,
    ZabbixTaskOut,
    ZabbixTaskUpdate,
    ZabbixTimelinePoint,
    ZabbixTopHost,
    ZabbixTopServer,
    ZabbixTriggerOut,
)
from app.services.zabbix.zabbix_service import zabbix_service

router = APIRouter()
logger = structlog.get_logger()

# All SOC roles can read Zabbix data
_ROLES = ["Super Admin", "SOC Analyst", "Manager", "Auditor", "IT Admin"]
# Write roles: only admins can create/update/delete
_WRITE_ROLES = ["Super Admin", "IT Admin", "Manager"]


def _check_enabled() -> None:
    if not settings.ZABBIX_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Zabbix integration is disabled (ZABBIX_ENABLED=false)",
        )


# =========================================================================
# /overview  (NEW)
# =========================================================================

@router.get(
    "/overview",
    response_model=ZabbixOverviewResponse,
    summary="Infrastructure overview KPI cards",
    tags=["Zabbix"],
)
async def zabbix_overview(
    _: User = Depends(require_roles(_ROLES)),
    __: User = Depends(require_password_changed),
) -> ZabbixOverviewResponse:
    """
    Returns extended infrastructure overview:
    - Total / online / offline / warning / critical server counts
    - Health score and grade
    - Total / critical / disaster / unacknowledged problem counts
    """
    _check_enabled()
    logger.info("zabbix_api_overview")
    return await zabbix_service.get_overview()


# =========================================================================
# /summary
# =========================================================================

@router.get(
    "/summary",
    response_model=ZabbixSummaryResponse,
    summary="Zabbix host + problem summary with health score",
    tags=["Zabbix"],
)
async def zabbix_summary(
    _: User = Depends(require_roles(_ROLES)),
    __: User = Depends(require_password_changed),
) -> ZabbixSummaryResponse:
    """
    Returns:
    - Total / available / unavailable / unknown host counts
    - Active problem counts by severity
    - Infrastructure Health Score (0–100) with grade
    """
    _check_enabled()
    logger.info("zabbix_api_summary")
    return await zabbix_service.get_summary()


# =========================================================================
# /hosts
# =========================================================================

@router.get(
    "/hosts",
    response_model=List[ZabbixHostOut],
    summary="List all Zabbix monitored hosts",
    tags=["Zabbix"],
)
async def zabbix_hosts(
    _: User = Depends(require_roles(_ROLES)),
    __: User = Depends(require_password_changed),
) -> List[ZabbixHostOut]:
    _check_enabled()
    logger.info("zabbix_api_hosts")
    return await zabbix_service.get_hosts()


# =========================================================================
# /problems
# =========================================================================

@router.get(
    "/problems",
    response_model=List[ZabbixProblemOut],
    summary="List active Zabbix problems",
    tags=["Zabbix"],
)
async def zabbix_problems(
    _: User = Depends(require_roles(_ROLES)),
    __: User = Depends(require_password_changed),
) -> List[ZabbixProblemOut]:
    _check_enabled()
    logger.info("zabbix_api_problems")
    return await zabbix_service.get_problems()


# =========================================================================
# /triggers
# =========================================================================

@router.get(
    "/triggers",
    response_model=List[ZabbixTriggerOut],
    summary="List Zabbix trigger states",
    tags=["Zabbix"],
)
async def zabbix_triggers(
    _: User = Depends(require_roles(_ROLES)),
    __: User = Depends(require_password_changed),
) -> List[ZabbixTriggerOut]:
    _check_enabled()
    logger.info("zabbix_api_triggers")
    return await zabbix_service.get_triggers()


# =========================================================================
# /events
# =========================================================================

@router.get(
    "/events",
    response_model=List[Dict[str, Any]],
    summary="Recent Zabbix events (last 24h)",
    tags=["Zabbix"],
)
async def zabbix_events(
    _: User = Depends(require_roles(_ROLES)),
    __: User = Depends(require_password_changed),
) -> List[Dict[str, Any]]:
    _check_enabled()
    logger.info("zabbix_api_events")
    return await zabbix_service.get_events()


# =========================================================================
# /severity
# =========================================================================

@router.get(
    "/severity",
    response_model=List[ZabbixSeverityDistribution],
    summary="Problem count by severity level",
    tags=["Zabbix"],
)
async def zabbix_severity(
    _: User = Depends(require_roles(_ROLES)),
    __: User = Depends(require_password_changed),
) -> List[ZabbixSeverityDistribution]:
    _check_enabled()
    logger.info("zabbix_api_severity")
    return await zabbix_service.get_severity_distribution()


# =========================================================================
# /top-hosts
# =========================================================================

@router.get(
    "/top-hosts",
    response_model=List[ZabbixTopHost],
    summary="Top hosts by active problem count",
    tags=["Zabbix"],
)
async def zabbix_top_hosts(
    limit: int = Query(default=10, ge=1, le=50, description="Number of hosts to return"),
    _: User = Depends(require_roles(_ROLES)),
    __: User = Depends(require_password_changed),
) -> List[ZabbixTopHost]:
    _check_enabled()
    logger.info("zabbix_api_top_hosts", limit=limit)
    return await zabbix_service.get_top_hosts(limit=limit)


# =========================================================================
# /top-servers  (NEW — top 10 by CPU/RAM/Disk)
# =========================================================================

@router.get(
    "/top-servers",
    response_model=List[ZabbixTopServer],
    summary="Top 10 servers by CPU / RAM / Disk utilization",
    tags=["Zabbix"],
)
async def zabbix_top_servers(
    limit: int = Query(default=10, ge=1, le=50),
    _: User = Depends(require_roles(_ROLES)),
    __: User = Depends(require_password_changed),
) -> List[ZabbixTopServer]:
    """Returns top N hosts ranked by CPU utilization (highest first)."""
    _check_enabled()
    logger.info("zabbix_api_top_servers", limit=limit)
    return await zabbix_service.get_top_servers(limit=limit)


# =========================================================================
# /resource-usage
# =========================================================================

@router.get(
    "/resource-usage",
    response_model=List[ZabbixResourceUsage],
    summary="CPU / Memory / Disk usage per host",
    tags=["Zabbix"],
)
async def zabbix_resource_usage(
    _: User = Depends(require_roles(_ROLES)),
    __: User = Depends(require_password_changed),
) -> List[ZabbixResourceUsage]:
    _check_enabled()
    logger.info("zabbix_api_resource_usage")
    return await zabbix_service.get_resource_usage()


# =========================================================================
# /resources  (alias for resource-usage — matches spec)
# =========================================================================

@router.get(
    "/resources",
    response_model=List[ZabbixResourceUsage],
    summary="Resource utilization alias (same as /resource-usage)",
    tags=["Zabbix"],
)
async def zabbix_resources(
    _: User = Depends(require_roles(_ROLES)),
    __: User = Depends(require_password_changed),
) -> List[ZabbixResourceUsage]:
    _check_enabled()
    logger.info("zabbix_api_resources")
    return await zabbix_service.get_resource_usage()


# =========================================================================
# /availability
# =========================================================================

@router.get(
    "/availability",
    response_model=List[ZabbixAvailabilitySummary],
    summary="Host availability / uptime status",
    tags=["Zabbix"],
)
async def zabbix_availability(
    _: User = Depends(require_roles(_ROLES)),
    __: User = Depends(require_password_changed),
) -> List[ZabbixAvailabilitySummary]:
    _check_enabled()
    logger.info("zabbix_api_availability")
    return await zabbix_service.get_availability()


# =========================================================================
# /timeline
# =========================================================================

@router.get(
    "/timeline",
    response_model=List[ZabbixTimelinePoint],
    summary="Problem count timeline (hourly buckets)",
    tags=["Zabbix"],
)
async def zabbix_timeline(
    hours: int = Query(default=24, ge=1, le=168, description="Lookback window in hours"),
    _: User = Depends(require_roles(_ROLES)),
    __: User = Depends(require_password_changed),
) -> List[ZabbixTimelinePoint]:
    _check_enabled()
    logger.info("zabbix_api_timeline", hours=hours)
    return await zabbix_service.get_timeline(hours=hours)


# =========================================================================
# /charts  (bundle endpoint)
# =========================================================================

@router.get(
    "/charts",
    response_model=ZabbixChartsResponse,
    summary="All Zabbix chart data in one response",
    tags=["Zabbix"],
)
async def zabbix_charts(
    _: User = Depends(require_roles(_ROLES)),
    __: User = Depends(require_password_changed),
) -> ZabbixChartsResponse:
    _check_enabled()
    logger.info("zabbix_api_charts")
    return await zabbix_service.get_charts()


# =========================================================================
# /assets  (NEW — Asset Management CRUD)
# =========================================================================

@router.get(
    "/assets",
    response_model=List[ZabbixAssetOut],
    summary="List all assets in the infrastructure inventory",
    tags=["Zabbix - Assets"],
)
async def list_assets(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(_ROLES)),
    __: User = Depends(require_password_changed),
) -> List[ZabbixAssetOut]:
    logger.info("zabbix_api_assets_list")
    return await zabbix_service.get_assets(db)


@router.post(
    "/assets",
    response_model=ZabbixAssetOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new asset record",
    tags=["Zabbix - Assets"],
)
async def create_asset(
    data: ZabbixAssetCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(_WRITE_ROLES)),
    __: User = Depends(require_password_changed),
) -> ZabbixAssetOut:
    logger.info("zabbix_api_asset_create", hostname=data.hostname)
    return await zabbix_service.create_asset(db, data)


@router.put(
    "/assets/{asset_id}",
    response_model=ZabbixAssetOut,
    summary="Update an existing asset record",
    tags=["Zabbix - Assets"],
)
async def update_asset(
    asset_id: str,
    data: ZabbixAssetUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(_WRITE_ROLES)),
    __: User = Depends(require_password_changed),
) -> ZabbixAssetOut:
    result = await zabbix_service.update_asset(db, asset_id, data)
    if not result:
        raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")
    return result


@router.delete(
    "/assets/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an asset record",
    tags=["Zabbix - Assets"],
)
async def delete_asset(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(_WRITE_ROLES)),
    __: User = Depends(require_password_changed),
) -> None:
    deleted = await zabbix_service.delete_asset(db, asset_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")


# =========================================================================
# /maintenance  (NEW — Maintenance Schedule CRUD)
# =========================================================================

@router.get(
    "/maintenance",
    response_model=List[ZabbixMaintenanceOut],
    summary="List all maintenance schedule entries",
    tags=["Zabbix - Maintenance"],
)
async def list_maintenance(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(_ROLES)),
    __: User = Depends(require_password_changed),
) -> List[ZabbixMaintenanceOut]:
    logger.info("zabbix_api_maintenance_list")
    return await zabbix_service.get_maintenance(db)


@router.post(
    "/maintenance",
    response_model=ZabbixMaintenanceOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new maintenance schedule entry",
    tags=["Zabbix - Maintenance"],
)
async def create_maintenance(
    data: ZabbixMaintenanceCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(_WRITE_ROLES)),
    __: User = Depends(require_password_changed),
) -> ZabbixMaintenanceOut:
    logger.info("zabbix_api_maintenance_create", hostname=data.hostname)
    return await zabbix_service.create_maintenance(db, data)


@router.put(
    "/maintenance/{maint_id}",
    response_model=ZabbixMaintenanceOut,
    summary="Update a maintenance schedule entry",
    tags=["Zabbix - Maintenance"],
)
async def update_maintenance(
    maint_id: str,
    data: ZabbixMaintenanceUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(_WRITE_ROLES)),
    __: User = Depends(require_password_changed),
) -> ZabbixMaintenanceOut:
    result = await zabbix_service.update_maintenance(db, maint_id, data)
    if not result:
        raise HTTPException(status_code=404, detail=f"Maintenance entry {maint_id} not found")
    return result


@router.delete(
    "/maintenance/{maint_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a maintenance schedule entry",
    tags=["Zabbix - Maintenance"],
)
async def delete_maintenance(
    maint_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(_WRITE_ROLES)),
    __: User = Depends(require_password_changed),
) -> None:
    deleted = await zabbix_service.delete_maintenance(db, maint_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Maintenance entry {maint_id} not found")


# =========================================================================
# /tasks  (NEW — Task Recommendations)
# =========================================================================

@router.get(
    "/tasks",
    response_model=List[ZabbixTaskOut],
    summary="Server task recommendations (auto-generated + manual)",
    tags=["Zabbix - Tasks"],
)
async def list_tasks(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(_ROLES)),
    __: User = Depends(require_password_changed),
) -> List[ZabbixTaskOut]:
    _check_enabled()
    logger.info("zabbix_api_tasks_list")
    return await zabbix_service.get_tasks(db)


@router.put(
    "/tasks/{task_id}",
    response_model=ZabbixTaskOut,
    summary="Update task status or priority",
    tags=["Zabbix - Tasks"],
)
async def update_task(
    task_id: str,
    data: ZabbixTaskUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(_WRITE_ROLES)),
    __: User = Depends(require_password_changed),
) -> ZabbixTaskOut:
    result = await zabbix_service.update_task(db, task_id, data)
    if not result:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return result


# =========================================================================
# /notifications  (NEW — Email Notification Log)
# =========================================================================

@router.get(
    "/notifications",
    response_model=List[ZabbixNotificationOut],
    summary="Email notification log",
    tags=["Zabbix - Notifications"],
)
async def list_notifications(
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(_ROLES)),
    __: User = Depends(require_password_changed),
) -> List[ZabbixNotificationOut]:
    logger.info("zabbix_api_notifications_list")
    return await zabbix_service.get_notifications(db, limit=limit)


@router.post(
    "/notifications/test",
    response_model=ZabbixNotificationOut,
    summary="Send a test email notification",
    tags=["Zabbix - Notifications"],
)
async def test_notification(
    body: ZabbixNotificationTestRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(_WRITE_ROLES)),
    __: User = Depends(require_password_changed),
) -> ZabbixNotificationOut:
    logger.info("zabbix_api_test_notification", email=body.email)
    return await zabbix_service.send_test_notification(db, body.email)
