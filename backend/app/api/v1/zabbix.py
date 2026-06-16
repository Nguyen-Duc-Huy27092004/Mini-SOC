"""
Zabbix API Routes — /api/v1/zabbix/*

All 11 endpoints:
  GET /summary          — host + problem counts + health score
  GET /hosts            — list of all monitored hosts
  GET /problems         — active problems with severity
  GET /triggers         — trigger states
  GET /events           — recent events (24h)
  GET /severity         — severity distribution
  GET /top-hosts        — top problem hosts (ranked)
  GET /resource-usage   — CPU / Memory / Disk per host
  GET /availability     — per-host availability status
  GET /timeline         — hourly problem timeline
  GET /charts           — all chart data bundled

Auth: same pattern as Wazuh routes (require_roles + require_password_changed).
Graceful fallback: when Zabbix is offline, returns empty data rather than 500.
"""
from __future__ import annotations

from typing import Any, Dict, List

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.config import settings
from app.core.security import require_password_changed, require_roles
from app.models.user import User
from app.schemas.zabbix import (
    ZabbixAvailabilitySummary,
    ZabbixChartsResponse,
    ZabbixHostOut,
    ZabbixProblemOut,
    ZabbixResourceUsage,
    ZabbixSeverityDistribution,
    ZabbixSummaryResponse,
    ZabbixTimelinePoint,
    ZabbixTopHost,
    ZabbixTriggerOut,
)
from app.services.zabbix.zabbix_service import zabbix_service

router = APIRouter()
logger = structlog.get_logger()

# All SOC roles can read Zabbix data
_ROLES = ["Super Admin", "SOC Analyst", "Manager", "Auditor", "IT Admin"]


def _check_enabled() -> None:
    if not settings.ZABBIX_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Zabbix integration is disabled (ZABBIX_ENABLED=false)",
        )


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
    """
    Returns all monitored hosts with:
    - Availability status (Available / Unavailable / Unknown)
    - Active problem count
    - Maximum severity among active problems
    """
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
    """
    Returns active (unresolved) problems with:
    - Human-readable severity label (Warning / Average / High / Disaster)
    - Acknowledgement status
    - Suppression status
    - Host name resolved from trigger
    - Event timestamp as ISO-8601 datetime
    """
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
    """
    Returns all triggers with:
    - Priority label (Not classified → Disaster)
    - Current value (OK / Problem)
    - Associated host name
    - Last state change timestamp
    """
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
    """
    Returns recent trigger state-change events (last 24 hours).
    Timestamps are ISO-8601. Priority converted to label.
    """
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
    """
    Returns active problem counts per severity level.
    Suitable for pie/donut chart in the dashboard.
    """
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
    """
    Returns top N hosts ranked by active problem count.
    Suitable for horizontal bar chart.
    """
    _check_enabled()
    logger.info("zabbix_api_top_hosts", limit=limit)
    return await zabbix_service.get_top_hosts(limit=limit)


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
    """
    Returns resource utilization percentages per host (where available).
    Values extracted from Zabbix items matching standard CPU / memory / disk keys.
    Null values indicate the metric is not collected for that host.
    """
    _check_enabled()
    logger.info("zabbix_api_resource_usage")
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
    """
    Returns per-host availability status:
    - Available: agent responding
    - Unavailable: agent not responding
    - Unknown: status undetermined
    """
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
    """
    Returns problems aggregated into hourly buckets for the given window.
    Suitable for area line chart.
    """
    _check_enabled()
    logger.info("zabbix_api_timeline", hours=hours)
    return await zabbix_service.get_timeline(hours=hours)


# =========================================================================
# /charts  (bundle endpoint — minimizes frontend round-trips)
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
    """
    Bundled chart data endpoint — returns severity distribution,
    top hosts, timeline, and resource usage in a single HTTP call.
    Optimized for dashboard initial load.
    """
    _check_enabled()
    logger.info("zabbix_api_charts")
    return await zabbix_service.get_charts()
