"""
Zabbix Data Mapper.

Maps normalized parser output into Pydantic response schemas.
Computes derived metrics:
  - Infrastructure Health Score (0-100)
  - Top problem hosts
  - Severity distribution
  - Resource usage from items
  - Problem timeline bucketed by hour
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.schemas.zabbix import (
    ZabbixAvailabilitySummary,
    ZabbixHealthScore,
    ZabbixHostOut,
    ZabbixHostSummary,
    ZabbixProblemOut,
    ZabbixResourceUsage,
    ZabbixSeverityDistribution,
    ZabbixTimelinePoint,
    ZabbixTopHost,
    ZabbixTriggerOut,
)
from app.services.zabbix.zabbix_parser import PRIORITY_MAP, PRIORITY_COLOR


# =========================================================================
# Host Summary
# =========================================================================

def map_host_summary(hosts: List[Dict[str, Any]]) -> ZabbixHostSummary:
    total = len(hosts)
    available = sum(1 for h in hosts if h.get("available_code") == 1)
    unavailable = sum(1 for h in hosts if h.get("available_code") == 2)
    unknown = sum(1 for h in hosts if h.get("available_code") == 0)
    return ZabbixHostSummary(
        total=total,
        available=available,
        unavailable=unavailable,
        unknown=unknown,
    )


# =========================================================================
# Host List
# =========================================================================

def map_hosts(hosts: List[Dict[str, Any]], problems: List[Dict[str, Any]]) -> List[ZabbixHostOut]:
    # Count problems per host via object_id (trigger objectid maps to trigger, not host directly)
    # We use host_id from triggers/problems where available
    host_problem_count: Counter = Counter()
    host_max_sev: Dict[str, int] = {}

    for p in problems:
        obj_id = p.get("object_id", "")
        sev = p.get("severity", 0)
        host_problem_count[obj_id] += 1
        host_max_sev[obj_id] = max(host_max_sev.get(obj_id, 0), sev)

    result = []
    for h in hosts:
        host_id = h["host_id"]
        problem_count = host_problem_count.get(host_id, 0)
        max_sev = host_max_sev.get(host_id, 0)
        result.append(ZabbixHostOut(
            host_id=host_id,
            name=h["name"],
            status=h["status"],
            available=h["available"],
            available_label=h["available_label"],
            ip_address=h.get("ip_address"),
            groups=h.get("groups", []),
            problem_count=problem_count,
            max_severity=max_sev,
            max_severity_label=PRIORITY_MAP.get(max_sev, "Not classified"),
        ))

    result.sort(key=lambda x: (x.problem_count, x.max_severity), reverse=True)
    return result


# =========================================================================
# Problems
# =========================================================================

def map_problems(
    problems: List[Dict[str, Any]],
    triggers: List[Dict[str, Any]],
) -> List[ZabbixProblemOut]:
    # Build trigger → host lookup
    trigger_host: Dict[str, str] = {}
    for t in triggers:
        trigger_host[t.get("trigger_id", "")] = t.get("host_name", "")

    result = []
    for p in problems:
        host_name = trigger_host.get(p.get("object_id", ""), "Unknown host")
        result.append(ZabbixProblemOut(
            event_id=p["event_id"],
            name=p["name"],
            severity=p["severity"],
            severity_label=p["severity_label"],
            severity_color=p["severity_color"],
            acknowledged=p["acknowledged"],
            suppressed=p["suppressed"],
            clock=p["clock"],
            clock_iso=p.get("clock_iso"),
            host_name=host_name,
            tags=p.get("tags", []),
        ))
    return result


# =========================================================================
# Triggers
# =========================================================================

def map_triggers(triggers: List[Dict[str, Any]]) -> List[ZabbixTriggerOut]:
    return [
        ZabbixTriggerOut(
            trigger_id=t["trigger_id"],
            name=t["name"],
            priority=t["priority"],
            priority_label=t["priority_label"],
            priority_color=t["priority_color"],
            status=t["status"],
            value=t["value"],
            value_label=t["value_label"],
            is_problem=t["is_problem"],
            host_id=t["host_id"],
            host_name=t["host_name"],
            last_change=t["last_change"],
            last_change_iso=t.get("last_change_iso"),
        )
        for t in triggers
    ]


# =========================================================================
# Severity Distribution
# =========================================================================

def map_severity_distribution(problems: List[Dict[str, Any]]) -> List[ZabbixSeverityDistribution]:
    counter: Counter = Counter()
    for p in problems:
        sev = p.get("severity", 0)
        counter[sev] += 1

    result = []
    for sev_int in range(6):
        count = counter.get(sev_int, 0)
        if count > 0:
            result.append(ZabbixSeverityDistribution(
                severity=sev_int,
                severity_label=PRIORITY_MAP.get(sev_int, "Not classified"),
                severity_color=PRIORITY_COLOR.get(sev_int, "#94a3b8"),
                count=count,
            ))
    return result


# =========================================================================
# Top Problem Hosts
# =========================================================================

def map_top_hosts(
    problems: List[Dict[str, Any]],
    triggers: List[Dict[str, Any]],
    limit: int = 10,
) -> List[ZabbixTopHost]:
    trigger_host: Dict[str, str] = {
        t.get("trigger_id", ""): t.get("host_name", "Unknown")
        for t in triggers
    }

    host_count: Counter = Counter()
    host_max_sev: Dict[str, int] = {}

    for p in problems:
        obj_id = p.get("object_id", "")
        host_name = trigger_host.get(obj_id, "Unknown host")
        sev = p.get("severity", 0)
        host_count[host_name] += 1
        host_max_sev[host_name] = max(host_max_sev.get(host_name, 0), sev)

    top = host_count.most_common(limit)
    return [
        ZabbixTopHost(
            host_name=name,
            problem_count=count,
            max_severity=host_max_sev.get(name, 0),
            max_severity_label=PRIORITY_MAP.get(host_max_sev.get(name, 0), "Not classified"),
            max_severity_color=PRIORITY_COLOR.get(host_max_sev.get(name, 0), "#94a3b8"),
        )
        for name, count in top
    ]


# =========================================================================
# Resource Usage from Items
# =========================================================================

_CPU_KEYS = ("system.cpu.util", "vm.cpu.util", "proc.cpu.util")
_MEM_KEYS = ("vm.memory.utilization", "memory.util.used", "vm.memory.size[pused]")
_DISK_KEYS = ("vfs.fs.size[/,pused]", "system.disk.usage", "perf_counter_en[\\PhysicalDisk(_Total)\\% Disk Time]")


def _match_key(item_key: str, patterns: tuple) -> bool:
    k = item_key.lower()
    return any(pat.lower() in k for pat in patterns)


def map_resource_usage(
    items: List[Dict[str, Any]],
    hosts: List[Dict[str, Any]],
) -> List[ZabbixResourceUsage]:
    host_name_map = {h["host_id"]: h["name"] for h in hosts}

    cpu: Dict[str, float] = {}
    mem: Dict[str, float] = {}
    disk: Dict[str, float] = {}

    for item in items:
        hid = item.get("host_id", "")
        key = item.get("key", "")
        val = item.get("last_value")
        if val is None:
            continue
        if _match_key(key, _CPU_KEYS) and hid not in cpu:
            cpu[hid] = min(float(val), 100.0)
        elif _match_key(key, _MEM_KEYS) and hid not in mem:
            mem[hid] = min(float(val), 100.0)
        elif _match_key(key, _DISK_KEYS) and hid not in disk:
            disk[hid] = min(float(val), 100.0)

    all_host_ids = set(list(cpu.keys()) + list(mem.keys()) + list(disk.keys()))
    result = []
    for hid in all_host_ids:
        result.append(ZabbixResourceUsage(
            host_id=hid,
            host_name=host_name_map.get(hid, hid),
            cpu_pct=cpu.get(hid),
            mem_pct=mem.get(hid),
            disk_pct=disk.get(hid),
        ))
    result.sort(key=lambda x: (x.cpu_pct or 0) + (x.mem_pct or 0), reverse=True)
    return result


# =========================================================================
# Availability Summary
# =========================================================================

def map_availability(hosts: List[Dict[str, Any]]) -> List[ZabbixAvailabilitySummary]:
    return [
        ZabbixAvailabilitySummary(
            host_id=h["host_id"],
            host_name=h["name"],
            available=h["available"],
            available_label=h["available_label"],
            available_code=h["available_code"],
            groups=h.get("groups", []),
        )
        for h in hosts
    ]


# =========================================================================
# Problem Timeline (hourly buckets for last 24h)
# =========================================================================

def map_timeline(
    problems: List[Dict[str, Any]],
    hours: int = 24,
) -> List[ZabbixTimelinePoint]:
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=hours)

    # Bucket by hour × severity
    buckets: Dict[str, Counter] = defaultdict(Counter)

    for p in problems:
        clock = p.get("clock")
        if not clock or clock < since:
            continue
        # Truncate to hour
        hour_key = clock.strftime("%H:%M")
        sev = p.get("severity", 0)
        buckets[hour_key][sev] += 1

    result = []
    for hour_key, sev_counter in sorted(buckets.items()):
        total = sum(sev_counter.values())
        max_sev = max(sev_counter.keys(), default=0)
        result.append(ZabbixTimelinePoint(
            timestamp=hour_key,
            count=total,
            severity=max_sev,
            severity_label=PRIORITY_MAP.get(max_sev, "Not classified"),
        ))
    return result


# =========================================================================
# Infrastructure Health Score
# =========================================================================

def map_health_score(
    hosts: List[Dict[str, Any]],
    problems: List[Dict[str, Any]],
) -> ZabbixHealthScore:
    total = len(hosts)
    if total == 0:
        return ZabbixHealthScore(score=0, grade="F", breakdown={
            "availability": 0,
            "problem_free": 0,
            "critical_penalty": 0,
        })

    # Availability component (40 points max)
    available = sum(1 for h in hosts if h.get("available_code") == 1)
    avail_score = (available / total) * 40

    # Problem-free component (40 points max)
    total_problems = len(problems)
    problem_ratio = min(total_problems / max(total, 1), 1.0)
    problem_score = (1 - problem_ratio) * 40

    # Critical / Disaster penalty (up to -20)
    disaster = sum(1 for p in problems if p.get("severity", 0) == 5)
    high = sum(1 for p in problems if p.get("severity", 0) == 4)
    penalty = min((disaster * 4 + high * 2), 20)
    critical_score = 20 - penalty

    score = round(avail_score + problem_score + critical_score)
    score = max(0, min(100, score))

    if score >= 90:
        grade = "A"
    elif score >= 75:
        grade = "B"
    elif score >= 60:
        grade = "C"
    elif score >= 40:
        grade = "D"
    else:
        grade = "F"

    return ZabbixHealthScore(
        score=score,
        grade=grade,
        breakdown={
            "availability": round(avail_score),
            "problem_free": round(problem_score),
            "critical_penalty": round(critical_score),
        },
    )
