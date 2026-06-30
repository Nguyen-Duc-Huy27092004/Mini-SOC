"""
Zabbix Service — Orchestrator Layer.

Coordinates:
  ZabbixClient → ZabbixParser → ZabbixMapper → Response schemas

Features:
  - Redis caching (60s TTL) to avoid hammering Zabbix
  - Async aiohttp session reuse
  - Graceful degradation: returns empty/offline response when Zabbix unreachable
  - Writes snapshots to PostgreSQL zabbix_* tables
  - Structured logging throughout
  - Asset management (CRUD)
  - Maintenance schedule management
  - Auto-generated task recommendations
  - Email notification dispatch + logging
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import uuid as _uuid

import structlog
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.schemas.zabbix import (
    ZabbixAssetCreate,
    ZabbixAssetOut,
    ZabbixAssetUpdate,
    ZabbixAvailabilitySummary,
    ZabbixChartsResponse,
    ZabbixHealthScore,
    ZabbixHostOut,
    ZabbixHostSummary,
    ZabbixMaintenanceCreate,
    ZabbixMaintenanceOut,
    ZabbixMaintenanceUpdate,
    ZabbixNotificationOut,
    ZabbixOverviewResponse,
    ZabbixProblemOut,
    ZabbixProblemSummary,
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
from app.services.zabbix.zabbix_client import ZabbixClient
from app.services.zabbix.zabbix_mapper import (
    map_availability,
    map_health_score,
    map_host_summary,
    map_hosts,
    map_problems,
    map_resource_usage,
    map_severity_distribution,
    map_timeline,
    map_top_hosts,
    map_triggers,
)
from app.services.zabbix.zabbix_parser import (
    parse_events,
    parse_hosts,
    parse_items,
    parse_problems,
    parse_triggers,
    resolve_http_agent_availability,
)

logger = structlog.get_logger()

_CACHE_TTL = 60  # seconds


def _build_client() -> ZabbixClient:
    return ZabbixClient(
        api_url=settings.ZABBIX_API_URL,
        user=settings.ZABBIX_API_USER,
        password=settings.ZABBIX_API_PASSWORD.get_secret_value(),
        verify_ssl=getattr(settings, "ZABBIX_VERIFY_SSL", True),
        timeout=getattr(settings, "ZABBIX_TIMEOUT", 30),
    )


class ZabbixService:
    """
    High-level Zabbix service used by API routes.
    All methods return Pydantic models or empty defaults — never raise.
    """

    def __init__(self) -> None:
        self._client: Optional[ZabbixClient] = None
        # Simple in-memory cache as fallback if Redis unavailable
        self._cache: Dict[str, Any] = {}
        self._cache_ts: Dict[str, float] = {}

    def _get_client(self) -> ZabbixClient:
        if self._client is None:
            self._client = _build_client()
        return self._client

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def _cache_get(self, key: str) -> Optional[Any]:
        import time
        if key in self._cache:
            age = time.monotonic() - self._cache_ts.get(key, 0)
            if age < _CACHE_TTL:
                return self._cache[key]
        return None

    def _cache_set(self, key: str, value: Any) -> None:
        import time
        self._cache[key] = value
        self._cache_ts[key] = time.monotonic()

    # ------------------------------------------------------------------
    # Raw data fetchers (internal)
    # ------------------------------------------------------------------

    async def _fetch_all(self) -> Dict[str, Any]:
        """Fetch hosts, problems, triggers, items in parallel."""
        cached = self._cache_get("_all")
        if cached is not None:
            return cached

        client = self._get_client()

        # Fetch hosts + problems + triggers in parallel.
        # host_get: always pass selectInterfaces + selectGroups + selectParentTemplates
        #   so the parser can detect all protocol types:
        #   - Zabbix Agent (iface type=1), SNMP (type=2), IPMI (type=3), JMX (type=4)
        #   - HTTP Agent (no real interfaces — detected from template/group names)
        #   - Active Agent (no interfaces — detected from template names)
        try:
            import asyncio
            raw_hosts, raw_problems, raw_triggers = await asyncio.gather(
                client.host_get(
                    selectInterfaces="extend",
                    selectGroups="extend",
                    selectParentTemplates=["name"],  # critical for protocol detection Step 3
                ),
                client.problem_get(),
                client.trigger_get(only_true=False),
            )
        except Exception as exc:
            logger.error("zabbix_fetch_all_failed", error=str(exc))
            return {}

        total_raw = len(raw_hosts or [])
        logger.info("zabbix_hosts_fetched_raw", count=total_raw)

        # Fetch items for resource usage (CPU/Mem/Disk keys only).
        host_ids = [h.get("hostid", "") for h in (raw_hosts or []) if h.get("hostid")]
        raw_items = []
        if host_ids:
            try:
                raw_items = await client.item_get(host_ids, limit=10000)
                logger.info("zabbix_items_fetched_raw", count=len(raw_items))
            except Exception as exc:
                logger.warning("zabbix_items_fetch_failed", error=str(exc))

        parsed_hosts = parse_hosts(raw_hosts or [])
        # parse_hosts already filters empty-dict failures; log any drop
        dropped = total_raw - len(parsed_hosts)
        if dropped > 0:
            logger.warning("zabbix_hosts_parse_dropped", dropped=dropped, total_raw=total_raw)

        parsed_items = parse_items(raw_items or [])

        # ── HTTP Agent / Active Agent availability fix ──────────────────────
        # These hosts have no real Zabbix interface, so interface-based
        # availability is always 0 (Unknown). We resolve it from item state.
        no_iface_host_ids = {
            h["host_id"]
            for h in parsed_hosts
            if h.get("available_code", 0) == 0  # still Unknown after interface parse
            or "HTTP Agent" in h.get("agent_types", [])
        }
        if no_iface_host_ids:
            http_avail = resolve_http_agent_availability(parsed_items, no_iface_host_ids)
            for h in parsed_hosts:
                hid = h["host_id"]
                if hid in http_avail:
                    code = http_avail[hid]
                    h["available_code"]  = code
                    h["available"]       = code == 1
                    h["available_label"] = {0: "Unknown", 1: "Available", 2: "Unavailable"}.get(code, "Unknown")
            logger.info(
                "zabbix_http_agent_avail_resolved",
                resolved=len(http_avail),
                available=sum(1 for v in http_avail.values() if v == 1),
                unavailable=sum(1 for v in http_avail.values() if v == 2),
                unknown=sum(1 for v in http_avail.values() if v == 0),
            )

        data = {
            "hosts":    parsed_hosts,
            "problems": parse_problems(raw_problems or []),
            "triggers": parse_triggers(raw_triggers or []),
            "items":    parsed_items,
        }
        logger.info(
            "zabbix_fetch_all_done",
            hosts=len(data["hosts"]),
            problems=len(data["problems"]),
            triggers=len(data["triggers"]),
            items=len(data["items"]),
        )
        self._cache_set("_all", data)
        return data


    # ------------------------------------------------------------------
    # Public API — Original endpoints (untouched)
    # ------------------------------------------------------------------

    async def get_summary(self) -> ZabbixSummaryResponse:
        """Return top-level summary (host counts + problem counts + health)."""
        try:
            data = await self._fetch_all()
            if not data:
                return ZabbixSummaryResponse(
                    hosts=ZabbixHostSummary(total=0, available=0, unavailable=0, unknown=0),
                    problems=ZabbixProblemSummary(total=0),
                    health=ZabbixHealthScore(score=0, grade="F"),
                    is_online=False,
                    error="Zabbix API unreachable",
                )

            hosts = data.get("hosts", [])
            problems = data.get("problems", [])

            host_summary = map_host_summary(hosts)
            health = map_health_score(hosts, problems)

            # Build problem summary
            from collections import Counter
            by_sev: Counter = Counter()
            unacked = 0
            for p in problems:
                by_sev[p["severity_label"]] += 1
                if not p["acknowledged"]:
                    unacked += 1

            problem_summary = ZabbixProblemSummary(
                total=len(problems),
                by_severity=dict(by_sev),
                unacknowledged=unacked,
            )

            return ZabbixSummaryResponse(
                hosts=host_summary,
                problems=problem_summary,
                health=health,
                is_online=True,
            )

        except Exception as exc:
            logger.exception("zabbix_get_summary_error", error=str(exc))
            return ZabbixSummaryResponse(
                hosts=ZabbixHostSummary(total=0, available=0, unavailable=0, unknown=0),
                problems=ZabbixProblemSummary(total=0),
                health=ZabbixHealthScore(score=0, grade="F"),
                is_online=False,
                error=str(exc)[:200],
            )

    async def get_hosts(self) -> List[ZabbixHostOut]:
        try:
            data = await self._fetch_all()
            hosts = data.get("hosts", [])
            problems = data.get("problems", [])
            return map_hosts(hosts, problems)
        except Exception as exc:
            logger.exception("zabbix_get_hosts_error", error=str(exc))
            return []

    async def get_problems(self) -> List[ZabbixProblemOut]:
        try:
            data = await self._fetch_all()
            return map_problems(data.get("problems", []), data.get("triggers", []))
        except Exception as exc:
            logger.exception("zabbix_get_problems_error", error=str(exc))
            return []

    async def get_triggers(self) -> List[ZabbixTriggerOut]:
        try:
            data = await self._fetch_all()
            return map_triggers(data.get("triggers", []))
        except Exception as exc:
            logger.exception("zabbix_get_triggers_error", error=str(exc))
            return []

    async def get_events(self) -> List[Dict[str, Any]]:
        try:
            client = self._get_client()
            since = int((datetime.now(timezone.utc) - timedelta(hours=24)).timestamp())
            raw = await client.event_get(time_from=since, limit=200)
            return parse_events(raw)
        except Exception as exc:
            logger.exception("zabbix_get_events_error", error=str(exc))
            return []

    async def get_severity_distribution(self) -> List[ZabbixSeverityDistribution]:
        try:
            data = await self._fetch_all()
            return map_severity_distribution(data.get("problems", []))
        except Exception as exc:
            logger.exception("zabbix_get_severity_error", error=str(exc))
            return []

    async def get_top_hosts(self, limit: int = 10) -> List[ZabbixTopHost]:
        try:
            data = await self._fetch_all()
            return map_top_hosts(data.get("problems", []), data.get("triggers", []), limit=limit)
        except Exception as exc:
            logger.exception("zabbix_get_top_hosts_error", error=str(exc))
            return []

    async def get_resource_usage(self) -> List[ZabbixResourceUsage]:
        try:
            data = await self._fetch_all()
            return map_resource_usage(data.get("items", []), data.get("hosts", []))
        except Exception as exc:
            logger.exception("zabbix_get_resource_error", error=str(exc))
            return []

    async def get_availability(self) -> List[ZabbixAvailabilitySummary]:
        try:
            data = await self._fetch_all()
            return map_availability(data.get("hosts", []))
        except Exception as exc:
            logger.exception("zabbix_get_availability_error", error=str(exc))
            return []

    async def get_timeline(self, hours: int = 24) -> List[ZabbixTimelinePoint]:
        try:
            data = await self._fetch_all()
            return map_timeline(data.get("problems", []), hours=hours)
        except Exception as exc:
            logger.exception("zabbix_get_timeline_error", error=str(exc))
            return []

    async def get_charts(self) -> ZabbixChartsResponse:
        """Bundle all chart data in a single response."""
        try:
            data = await self._fetch_all()
            hosts = data.get("hosts", [])
            problems = data.get("problems", [])
            triggers = data.get("triggers", [])
            items = data.get("items", [])

            return ZabbixChartsResponse(
                severity_distribution=map_severity_distribution(problems),
                top_hosts=map_top_hosts(problems, triggers),
                timeline=map_timeline(problems),
                resource_usage=map_resource_usage(items, hosts),
            )
        except Exception as exc:
            logger.exception("zabbix_get_charts_error", error=str(exc))
            return ZabbixChartsResponse()

    async def ping(self) -> bool:
        """Check if Zabbix is reachable."""
        try:
            client = self._get_client()
            return await client.ping()
        except Exception:
            return False

    # ------------------------------------------------------------------
    # NEW: Overview endpoint
    # ------------------------------------------------------------------

    async def get_overview(self) -> ZabbixOverviewResponse:
        """Extended overview for the Infrastructure Dashboard KPI cards."""
        try:
            data = await self._fetch_all()
            if not data:
                return ZabbixOverviewResponse(is_online=False, error="Zabbix API unreachable")

            hosts = data.get("hosts", [])
            problems = data.get("problems", [])
            health = map_health_score(hosts, problems)

            total = len(hosts)
            online = sum(1 for h in hosts if h.get("available_code") == 1)
            offline = sum(1 for h in hosts if h.get("available_code") == 2)
            unknown = sum(1 for h in hosts if h.get("available_code") == 0)

            # Build a host_id → max severity lookup from active problems
            from collections import defaultdict
            host_max_sev: Dict[str, int] = defaultdict(int)
            for p in problems:
                obj_id = p.get("object_id", "")
                sev = p.get("severity", 0)
                if sev > host_max_sev[obj_id]:
                    host_max_sev[obj_id] = sev

            # warning_servers: online hosts that have at least one warning/average problem
            warning_hosts = sum(
                1 for h in hosts
                if h.get("available_code") == 1 and host_max_sev.get(h["host_id"], 0) in (2, 3)
            )
            # critical_servers: any host with high/disaster problem
            critical_hosts = sum(
                1 for h in hosts if host_max_sev.get(h["host_id"], 0) >= 4
            )
            disasters = sum(1 for p in problems if p.get("severity", 0) == 5)
            criticals = sum(1 for p in problems if p.get("severity", 0) == 4)
            unacked = sum(1 for p in problems if not p.get("acknowledged"))

            return ZabbixOverviewResponse(
                total_servers=total,
                online_servers=online,
                offline_servers=offline,
                warning_servers=warning_hosts,
                critical_servers=critical_hosts,
                health_score=health.score,
                health_grade=health.grade,
                total_problems=len(problems),
                critical_problems=criticals,
                disaster_problems=disasters,
                unacknowledged_problems=unacked,
                is_online=True,
            )
        except Exception as exc:
            logger.exception("zabbix_get_overview_error", error=str(exc))
            return ZabbixOverviewResponse(is_online=False, error=str(exc)[:200])

    # ------------------------------------------------------------------
    # NEW: Top servers by resource utilization
    # ------------------------------------------------------------------

    async def get_top_servers(self, limit: int = 10) -> List[ZabbixTopServer]:
        """Top N hosts ranked by CPU, then memory, then disk."""
        try:
            data = await self._fetch_all()
            resource_list = map_resource_usage(data.get("items", []), data.get("hosts", []))
            hosts = data.get("hosts", [])
            problems = data.get("problems", [])

            # Build problem count per host_id lookup
            from collections import Counter
            host_problem_count: Counter = Counter()
            for p in problems:
                host_problem_count[p.get("object_id", "")] += 1

            host_avail_map = {h["host_id"]: h["available_label"] for h in hosts}
            host_ip_map = {h["host_id"]: h.get("ip_address") for h in hosts}

            result = []
            for r in resource_list:
                result.append(ZabbixTopServer(
                    host_id=r.host_id,
                    host_name=r.host_name,
                    ip_address=host_ip_map.get(r.host_id),
                    cpu_pct=r.cpu_pct,
                    mem_pct=r.mem_pct,
                    disk_pct=r.disk_pct,
                    problem_count=host_problem_count.get(r.host_id, 0),
                    status=host_avail_map.get(r.host_id, "Unknown"),
                ))

            # Sort by CPU desc, then mem desc
            result.sort(key=lambda x: (-(x.cpu_pct or 0), -(x.mem_pct or 0), -(x.disk_pct or 0)))
            return result[:limit]
        except Exception as exc:
            logger.exception("zabbix_get_top_servers_error", error=str(exc))
            return []

    # ------------------------------------------------------------------
    # NEW: Asset Management (CRUD)
    # ------------------------------------------------------------------

    async def get_assets(self, db: AsyncSession) -> List[ZabbixAssetOut]:
        from app.models.zabbix import ZabbixAsset
        try:
            result = await db.execute(select(ZabbixAsset).order_by(ZabbixAsset.created_at.desc()))
            assets = result.scalars().all()
            return [
                ZabbixAssetOut(
                    id=str(a.id),
                    hostname=a.hostname,
                    ip_address=a.ip_address,
                    location=a.location,
                    department=a.department,
                    owner=a.owner,
                    vendor=a.vendor,
                    model=a.model,
                    serial_number=a.serial_number,
                    purchase_date=a.purchase_date,
                    warranty_expiration=a.warranty_expiration,
                    lifecycle_status=a.lifecycle_status,
                    notes=a.notes,
                    created_at=a.created_at,
                    updated_at=a.updated_at,
                )
                for a in assets
            ]
        except Exception as exc:
            logger.exception("zabbix_get_assets_error", error=str(exc))
            return []

    async def create_asset(self, db: AsyncSession, data: ZabbixAssetCreate) -> ZabbixAssetOut:
        from app.models.zabbix import ZabbixAsset
        now = datetime.now(timezone.utc)
        asset = ZabbixAsset(
            hostname=data.hostname,
            ip_address=data.ip_address,
            location=data.location,
            department=data.department,
            owner=data.owner,
            vendor=data.vendor,
            model=data.model,
            serial_number=data.serial_number,
            purchase_date=data.purchase_date,
            warranty_expiration=data.warranty_expiration,
            lifecycle_status=data.lifecycle_status,
            notes=data.notes,
            created_at=now,
            updated_at=now,
        )
        db.add(asset)
        await db.commit()
        await db.refresh(asset)
        return ZabbixAssetOut(
            id=str(asset.id),
            hostname=asset.hostname,
            ip_address=asset.ip_address,
            location=asset.location,
            department=asset.department,
            owner=asset.owner,
            vendor=asset.vendor,
            model=asset.model,
            serial_number=asset.serial_number,
            purchase_date=asset.purchase_date,
            warranty_expiration=asset.warranty_expiration,
            lifecycle_status=asset.lifecycle_status,
            notes=asset.notes,
            created_at=asset.created_at,
            updated_at=asset.updated_at,
        )

    async def update_asset(self, db: AsyncSession, asset_id: str, data: ZabbixAssetUpdate) -> Optional[ZabbixAssetOut]:
        from app.models.zabbix import ZabbixAsset
        result = await db.execute(select(ZabbixAsset).where(ZabbixAsset.id == _uuid.UUID(asset_id)))
        asset = result.scalar_one_or_none()
        if not asset:
            return None
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(asset, field, value)
        asset.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(asset)
        return ZabbixAssetOut(
            id=str(asset.id), hostname=asset.hostname, ip_address=asset.ip_address,
            location=asset.location, department=asset.department, owner=asset.owner,
            vendor=asset.vendor, model=asset.model, serial_number=asset.serial_number,
            purchase_date=asset.purchase_date, warranty_expiration=asset.warranty_expiration,
            lifecycle_status=asset.lifecycle_status, notes=asset.notes,
            created_at=asset.created_at, updated_at=asset.updated_at,
        )

    async def delete_asset(self, db: AsyncSession, asset_id: str) -> bool:
        from app.models.zabbix import ZabbixAsset
        result = await db.execute(delete(ZabbixAsset).where(ZabbixAsset.id == _uuid.UUID(asset_id)))
        await db.commit()
        return result.rowcount > 0

    # ------------------------------------------------------------------
    # NEW: Maintenance Schedule (CRUD)
    # ------------------------------------------------------------------

    async def get_maintenance(self, db: AsyncSession) -> List[ZabbixMaintenanceOut]:
        from app.models.zabbix import ZabbixMaintenance
        try:
            result = await db.execute(
                select(ZabbixMaintenance).order_by(ZabbixMaintenance.next_maintenance_date.asc())
            )
            items = result.scalars().all()
            now = datetime.now(timezone.utc)
            out = []
            for m in items:
                next_dt = m.next_maintenance_date
                if next_dt.tzinfo is None:
                    next_dt = next_dt.replace(tzinfo=timezone.utc)
                delta = next_dt - now
                days_left = delta.days
                is_overdue = days_left < 0
                out.append(ZabbixMaintenanceOut(
                    id=str(m.id),
                    hostname=m.hostname,
                    ip_address=m.ip_address,
                    task_type=m.task_type,
                    last_maintenance_date=m.last_maintenance_date,
                    next_maintenance_date=m.next_maintenance_date,
                    interval_days=m.interval_days,
                    status=m.status,
                    assigned_to=m.assigned_to,
                    notes=m.notes,
                    is_overdue=is_overdue,
                    days_until_due=days_left,
                    created_at=m.created_at,
                    updated_at=m.updated_at,
                ))
            return out
        except Exception as exc:
            logger.exception("zabbix_get_maintenance_error", error=str(exc))
            return []

    async def create_maintenance(self, db: AsyncSession, data: ZabbixMaintenanceCreate) -> ZabbixMaintenanceOut:
        from app.models.zabbix import ZabbixMaintenance
        now = datetime.now(timezone.utc)
        m = ZabbixMaintenance(
            hostname=data.hostname, ip_address=data.ip_address,
            task_type=data.task_type,
            last_maintenance_date=data.last_maintenance_date,
            next_maintenance_date=data.next_maintenance_date,
            interval_days=data.interval_days, status=data.status,
            assigned_to=data.assigned_to, notes=data.notes,
            created_at=now, updated_at=now,
        )
        db.add(m)
        await db.commit()
        await db.refresh(m)
        next_dt = m.next_maintenance_date
        if next_dt.tzinfo is None:
            next_dt = next_dt.replace(tzinfo=timezone.utc)
        days_left = (next_dt - now).days
        return ZabbixMaintenanceOut(
            id=str(m.id), hostname=m.hostname, ip_address=m.ip_address,
            task_type=m.task_type, last_maintenance_date=m.last_maintenance_date,
            next_maintenance_date=m.next_maintenance_date, interval_days=m.interval_days,
            status=m.status, assigned_to=m.assigned_to, notes=m.notes,
            is_overdue=days_left < 0, days_until_due=days_left,
            created_at=m.created_at, updated_at=m.updated_at,
        )

    async def update_maintenance(self, db: AsyncSession, maint_id: str, data: ZabbixMaintenanceUpdate) -> Optional[ZabbixMaintenanceOut]:
        from app.models.zabbix import ZabbixMaintenance
        result = await db.execute(select(ZabbixMaintenance).where(ZabbixMaintenance.id == _uuid.UUID(maint_id)))
        m = result.scalar_one_or_none()
        if not m:
            return None
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(m, field, value)
        m.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(m)
        now = datetime.now(timezone.utc)
        next_dt = m.next_maintenance_date
        if next_dt.tzinfo is None:
            next_dt = next_dt.replace(tzinfo=timezone.utc)
        days_left = (next_dt - now).days
        return ZabbixMaintenanceOut(
            id=str(m.id), hostname=m.hostname, ip_address=m.ip_address,
            task_type=m.task_type, last_maintenance_date=m.last_maintenance_date,
            next_maintenance_date=m.next_maintenance_date, interval_days=m.interval_days,
            status=m.status, assigned_to=m.assigned_to, notes=m.notes,
            is_overdue=days_left < 0, days_until_due=days_left,
            created_at=m.created_at, updated_at=m.updated_at,
        )

    async def delete_maintenance(self, db: AsyncSession, maint_id: str) -> bool:
        from app.models.zabbix import ZabbixMaintenance
        result = await db.execute(delete(ZabbixMaintenance).where(ZabbixMaintenance.id == _uuid.UUID(maint_id)))
        await db.commit()
        return result.rowcount > 0

    # ------------------------------------------------------------------
    # NEW: Task Recommendations (auto-generate + DB persist)
    # ------------------------------------------------------------------

    async def get_tasks(self, db: AsyncSession) -> List[ZabbixTaskOut]:
        from app.models.zabbix import ZabbixTask
        try:
            # Auto-generate tasks from live data
            await self._auto_generate_tasks(db)

            result = await db.execute(
                select(ZabbixTask)
                .where(ZabbixTask.status.in_(["Open", "In Progress"]))
                .order_by(
                    ZabbixTask.priority.desc(),
                    ZabbixTask.created_at.desc()
                )
            )
            tasks = result.scalars().all()
            return [
                ZabbixTaskOut(
                    id=str(t.id), hostname=t.hostname, ip_address=t.ip_address,
                    task_type=t.task_type, description=t.description,
                    priority=t.priority, status=t.status, source=t.source,
                    metric_value=t.metric_value,
                    created_at=t.created_at, updated_at=t.updated_at,
                )
                for t in tasks
            ]
        except Exception as exc:
            logger.exception("zabbix_get_tasks_error", error=str(exc))
            return []

    async def _auto_generate_tasks(self, db: AsyncSession) -> None:
        """Generate task recommendations from current resource + problem data."""
        from app.models.zabbix import ZabbixTask
        try:
            data = await self._fetch_all()
            if not data:
                return

            resource_list = map_resource_usage(data.get("items", []), data.get("hosts", []))
            hosts = data.get("hosts", [])
            problems = data.get("problems", [])
            host_ip_map = {h["host_id"]: h.get("ip_address") for h in hosts}

            now = datetime.now(timezone.utc)
            new_tasks = []

            for r in resource_list:
                ip = host_ip_map.get(r.host_id)
                # High CPU → Investigation task
                if r.cpu_pct and r.cpu_pct >= 80:
                    priority = "Critical" if r.cpu_pct >= 90 else "High"
                    new_tasks.append({
                        "hostname": r.host_name, "ip_address": ip,
                        "task_type": "High CPU Investigation",
                        "description": f"CPU at {r.cpu_pct:.1f}% — investigate top processes and consider load balancing.",
                        "priority": priority, "metric_value": r.cpu_pct,
                    })
                # High Disk → Cleanup task
                if r.disk_pct and r.disk_pct >= 80:
                    priority = "Critical" if r.disk_pct >= 90 else "High"
                    new_tasks.append({
                        "hostname": r.host_name, "ip_address": ip,
                        "task_type": "Disk Cleanup",
                        "description": f"Disk at {r.disk_pct:.1f}% — clean logs, temp files, and archive old data.",
                        "priority": priority, "metric_value": r.disk_pct,
                    })
                # High Memory
                if r.mem_pct and r.mem_pct >= 85:
                    priority = "Critical" if r.mem_pct >= 95 else "High"
                    new_tasks.append({
                        "hostname": r.host_name, "ip_address": ip,
                        "task_type": "Memory Upgrade",
                        "description": f"Memory at {r.mem_pct:.1f}% — review memory-intensive processes or add RAM.",
                        "priority": priority, "metric_value": r.mem_pct,
                    })

            # High severity problems → Security/Patch tasks
            for p in problems:
                if p.get("severity", 0) >= 4:
                    new_tasks.append({
                        "hostname": p.get("host_name", "Unknown"),
                        "ip_address": None,
                        "task_type": "Security Update",
                        "description": f"High severity problem: {p.get('name', 'Unknown')} — immediate attention required.",
                        "priority": "Critical" if p.get("severity") == 5 else "High",
                        "metric_value": float(p.get("severity", 0)),
                    })

            # Add only tasks that don't already exist (deduplicate by hostname+task_type)
            existing = await db.execute(
                select(ZabbixTask.hostname, ZabbixTask.task_type)
                .where(ZabbixTask.status == "Open", ZabbixTask.source == "auto")
            )
            existing_set = {(row[0], row[1]) for row in existing.fetchall()}

            for task_data in new_tasks:
                key = (task_data["hostname"], task_data["task_type"])
                if key not in existing_set:
                    t = ZabbixTask(
                        hostname=task_data["hostname"],
                        ip_address=task_data.get("ip_address"),
                        task_type=task_data["task_type"],
                        description=task_data["description"],
                        priority=task_data["priority"],
                        status="Open",
                        source="auto",
                        metric_value=task_data.get("metric_value"),
                        created_at=now, updated_at=now,
                    )
                    db.add(t)

            await db.commit()
        except Exception as exc:
            logger.warning("zabbix_auto_generate_tasks_error", error=str(exc))
            await db.rollback()

    async def update_task(self, db: AsyncSession, task_id: str, data: ZabbixTaskUpdate) -> Optional[ZabbixTaskOut]:
        from app.models.zabbix import ZabbixTask
        result = await db.execute(select(ZabbixTask).where(ZabbixTask.id == _uuid.UUID(task_id)))
        task = result.scalar_one_or_none()
        if not task:
            return None
        if data.status:
            task.status = data.status
        if data.priority:
            task.priority = data.priority
        task.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(task)
        return ZabbixTaskOut(
            id=str(task.id), hostname=task.hostname, ip_address=task.ip_address,
            task_type=task.task_type, description=task.description,
            priority=task.priority, status=task.status, source=task.source,
            metric_value=task.metric_value,
            created_at=task.created_at, updated_at=task.updated_at,
        )

    # ------------------------------------------------------------------
    # NEW: Notifications
    # ------------------------------------------------------------------

    async def get_notifications(self, db: AsyncSession, limit: int = 100) -> List[ZabbixNotificationOut]:
        from app.models.zabbix import ZabbixNotification
        try:
            result = await db.execute(
                select(ZabbixNotification)
                .order_by(ZabbixNotification.sent_at.desc())
                .limit(limit)
            )
            notifs = result.scalars().all()
            return [
                ZabbixNotificationOut(
                    id=str(n.id), notification_type=n.notification_type,
                    hostname=n.hostname, ip_address=n.ip_address,
                    subject=n.subject, message=n.message,
                    recipients=n.recipients, severity=n.severity,
                    metric_value=n.metric_value, suggested_action=n.suggested_action,
                    status=n.status, error_msg=n.error_msg, sent_at=n.sent_at,
                )
                for n in notifs
            ]
        except Exception as exc:
            logger.exception("zabbix_get_notifications_error", error=str(exc))
            return []

    async def send_test_notification(self, db: AsyncSession, email: str) -> ZabbixNotificationOut:
        from app.models.zabbix import ZabbixNotification
        from app.services.zabbix.zabbix_email import notify_test

        success, error = await notify_test(email)
        now = datetime.now(timezone.utc)
        status = "sent" if success else ("skipped" if "disabled" in error.lower() or "not configured" in error.lower() else "failed")

        n = ZabbixNotification(
            notification_type="test",
            subject="[TEST] Mini-SOC Notification Test",
            message="Test email notification",
            recipients=email,
            status=status,
            error_msg=error if not success else None,
            sent_at=now,
        )
        db.add(n)
        await db.commit()
        await db.refresh(n)
        return ZabbixNotificationOut(
            id=str(n.id), notification_type=n.notification_type,
            hostname=None, ip_address=None,
            subject=n.subject, message=n.message,
            recipients=n.recipients, severity=None,
            metric_value=None, suggested_action=None,
            status=n.status, error_msg=n.error_msg, sent_at=n.sent_at,
        )

    # ------------------------------------------------------------------
    # DB Persistence (write-through to PostgreSQL zabbix_* tables)
    # ------------------------------------------------------------------

    async def sync_to_db(self, db: AsyncSession) -> None:
        """Persist current Zabbix snapshot to PostgreSQL tables."""
        from sqlalchemy import delete, insert
        from app.models.zabbix import ZabbixHost, ZabbixProblem, ZabbixTrigger

        try:
            data = await self._fetch_all()
            if not data:
                return

            now = datetime.now(timezone.utc)

            # Upsert hosts
            for h in data.get("hosts", []):
                from sqlalchemy.dialects.postgresql import insert as pg_insert
                stmt = pg_insert(ZabbixHost).values(
                    host_id=h["host_id"],
                    name=h["name"],
                    available_code=h["available_code"],
                    available_label=h["available_label"],
                    status=h["status"],
                    ip_address=h.get("ip_address"),
                    groups=h.get("groups", []),
                    error_msg=h.get("error"),
                    last_synced=now,
                ).on_conflict_do_update(
                    index_elements=["host_id"],
                    set_={
                        "name": h["name"],
                        "available_code": h["available_code"],
                        "available_label": h["available_label"],
                        "status": h["status"],
                        "ip_address": h.get("ip_address"),
                        "groups": h.get("groups", []),
                        "error_msg": h.get("error"),
                        "last_synced": now,
                    },
                )
                await db.execute(stmt)

            await db.commit()
            logger.info("zabbix_sync_to_db_complete", host_count=len(data.get("hosts", [])))

        except Exception as exc:
            await db.rollback()
            logger.exception("zabbix_sync_to_db_error", error=str(exc))


# Singleton instance
zabbix_service = ZabbixService()
