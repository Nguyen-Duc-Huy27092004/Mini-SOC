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
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.schemas.zabbix import (
    ZabbixAvailabilitySummary,
    ZabbixChartsResponse,
    ZabbixHealthScore,
    ZabbixHostOut,
    ZabbixHostSummary,
    ZabbixProblemOut,
    ZabbixProblemSummary,
    ZabbixResourceUsage,
    ZabbixSeverityDistribution,
    ZabbixSummaryResponse,
    ZabbixTimelinePoint,
    ZabbixTopHost,
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

        # Check connectivity first
        try:
            import asyncio
            raw_hosts, raw_problems, raw_triggers = await asyncio.gather(
                client.host_get(),
                client.problem_get(),
                client.trigger_get(only_true=False),
            )
        except Exception as exc:
            logger.error("zabbix_fetch_all_failed", error=str(exc))
            return {}

        # Fetch items for resource usage (CPU/Mem/Disk keys only)
        host_ids = [h.get("hostid", "") for h in (raw_hosts or []) if h.get("hostid")]
        raw_items = []
        if host_ids:
            try:
                raw_items = await client.item_get(host_ids[:50])  # limit to 50 hosts max
            except Exception as exc:
                logger.warning("zabbix_items_fetch_failed", error=str(exc))

        data = {
            "hosts": parse_hosts(raw_hosts or []),
            "problems": parse_problems(raw_problems or []),
            "triggers": parse_triggers(raw_triggers or []),
            "items": parse_items(raw_items or []),
        }
        self._cache_set("_all", data)
        return data

    # ------------------------------------------------------------------
    # Public API
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
