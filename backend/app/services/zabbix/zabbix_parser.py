"""
Zabbix Data Parser.

Converts raw Zabbix API responses into clean, normalized Python dicts.
Raw Zabbix data NEVER leaves this layer — all field names, types,
and sentinel values are normalized here before reaching the mapper.

Conversions:
  - Priority int → human-readable severity label
  - Unix timestamp (str/int) → datetime
  - Host availability int → label + boolean
  - Trigger value → status string
  - Remove: null values, internal IDs not needed by UI, duplicates
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# =========================================================================
# Priority / Severity Maps
# =========================================================================

PRIORITY_MAP: Dict[int, str] = {
    0: "Not classified",
    1: "Information",
    2: "Warning",
    3: "Average",
    4: "High",
    5: "Disaster",
}

PRIORITY_COLOR: Dict[int, str] = {
    0: "#94a3b8",   # slate
    1: "#22d3ee",   # cyan
    2: "#facc15",   # yellow
    3: "#fb923c",   # orange
    4: "#f87171",   # red-400
    5: "#dc2626",   # red-600
}

AVAILABILITY_MAP: Dict[int, str] = {
    0: "Unknown",
    1: "Available",
    2: "Unavailable",
}

# Interface type codes returned by Zabbix API
# type 1 = Agent, type 2 = SNMP, type 3 = IPMI, type 4 = JMX
_IFACE_AVAIL_FIELDS = [
    "available",      # Zabbix Agent (type 1)
    "snmp_available", # SNMP       (type 2)
    "ipmi_available", # IPMI       (type 3)
    "jmx_available",  # JMX        (type 4)
]

TRIGGER_VALUE_MAP: Dict[int, str] = {
    0: "OK",
    1: "Problem",
}

HOST_STATUS_MAP: Dict[int, str] = {
    0: "Monitored",
    1: "Not monitored",
}

ITEM_VALUE_TYPE: Dict[int, str] = {
    0: "Numeric (float)",
    1: "Character",
    2: "Log",
    3: "Numeric (unsigned)",
    4: "Text",
}


# =========================================================================
# Timestamp helpers
# =========================================================================

def _parse_unix(value: Any) -> Optional[datetime]:
    """Convert Unix timestamp (int or str) to UTC datetime."""
    if value is None:
        return None
    try:
        ts = int(value)
        if ts == 0:
            return None
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except (ValueError, TypeError, OSError):
        return None


def _unix_to_iso(value: Any) -> Optional[str]:
    """Convert Unix timestamp to ISO-8601 string."""
    dt = _parse_unix(value)
    return dt.isoformat() if dt else None


# =========================================================================
# Host Parser
# =========================================================================

def parse_host(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a single host record from host.get."""
    status_int = _safe_int(raw.get("status"), 0)

    # Compute composite availability across ALL interface types.
    # Zabbix tracks availability separately per interface protocol:
    #   available      -> Zabbix Agent (type 1)
    #   snmp_available -> SNMP         (type 2)
    #   ipmi_available -> IPMI         (type 3)
    #   jmx_available  -> JMX          (type 4)
    #
    # Resolution priority:  1 (Available) > 2 (Unavailable) > 0 (Unknown)
    # A host is Available if at least ONE active interface is reachable.
    avail_values = [
        _safe_int(raw.get(field), 0)
        for field in _IFACE_AVAIL_FIELDS
    ]
    avail_int = _resolve_composite_availability(avail_values)

    # Extract primary interface IP
    ip_address: Optional[str] = None
    interfaces = raw.get("interfaces") or []
    if isinstance(interfaces, list) and interfaces:
        ip_address = interfaces[0].get("ip")

    # Extract group names
    groups = raw.get("groups") or raw.get("hostGroups") or []
    group_names = [g.get("name", "") for g in groups if isinstance(g, dict)]

    return {
        "host_id": raw.get("hostid", ""),
        "name": raw.get("name") or raw.get("host", ""),
        "hostname": raw.get("host", ""),
        "status": HOST_STATUS_MAP.get(status_int, "Unknown"),
        "status_code": status_int,
        "available": avail_int == 1,
        "available_label": AVAILABILITY_MAP.get(avail_int, "Unknown"),
        "available_code": avail_int,
        "ip_address": ip_address,
        "groups": group_names,
        "error": raw.get("error") or None,
    }


def parse_hosts(raw_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize a list of hosts, removing duplicates by host_id."""
    seen: set[str] = set()
    result = []
    for raw in (raw_list or []):
        host_id = raw.get("hostid", "")
        if host_id in seen:
            continue
        seen.add(host_id)
        result.append(parse_host(raw))
    return result


# =========================================================================
# Problem Parser
# =========================================================================

def parse_problem(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a single problem record from problem.get."""
    sev_int = _safe_int(raw.get("severity"), 0)
    return {
        "event_id": raw.get("eventid", ""),
        "object_id": raw.get("objectid", ""),
        "name": raw.get("name") or raw.get("opdata") or "Unknown problem",
        "severity": sev_int,
        "severity_label": PRIORITY_MAP.get(sev_int, "Not classified"),
        "severity_color": PRIORITY_COLOR.get(sev_int, "#94a3b8"),
        "acknowledged": raw.get("acknowledged") == "1" or raw.get("acknowledged") is True,
        "suppressed": raw.get("suppressed") == "1",
        "clock": _parse_unix(raw.get("clock")),
        "clock_iso": _unix_to_iso(raw.get("clock")),
        "tags": [
            {"tag": t.get("tag", ""), "value": t.get("value", "")}
            for t in (raw.get("tags") or [])
            if isinstance(t, dict)
        ],
    }


def parse_problems(raw_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize and deduplicate problems."""
    seen: set[str] = set()
    result = []
    for raw in (raw_list or []):
        eid = raw.get("eventid", "")
        if eid in seen:
            continue
        seen.add(eid)
        result.append(parse_problem(raw))
    return result


# =========================================================================
# Trigger Parser
# =========================================================================

def parse_trigger(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a single trigger record from trigger.get."""
    prio_int = _safe_int(raw.get("priority"), 0)
    val_int = _safe_int(raw.get("value"), 0)

    # Extract host info from nested hosts array
    hosts = raw.get("hosts") or []
    host_name = hosts[0].get("name", "") if hosts else ""
    host_id = hosts[0].get("hostid", "") if hosts else ""

    return {
        "trigger_id": raw.get("triggerid", ""),
        "name": raw.get("description", ""),
        "priority": prio_int,
        "priority_label": PRIORITY_MAP.get(prio_int, "Not classified"),
        "priority_color": PRIORITY_COLOR.get(prio_int, "#94a3b8"),
        "status": "Enabled" if raw.get("status") == "0" else "Disabled",
        "value": val_int,
        "value_label": TRIGGER_VALUE_MAP.get(val_int, "Unknown"),
        "is_problem": val_int == 1,
        "host_id": host_id,
        "host_name": host_name,
        "last_change": _parse_unix(raw.get("lastchange")),
        "last_change_iso": _unix_to_iso(raw.get("lastchange")),
        "error": raw.get("error") or None,
    }


def parse_triggers(raw_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: set[str] = set()
    result = []
    for raw in (raw_list or []):
        tid = raw.get("triggerid", "")
        if tid in seen:
            continue
        seen.add(tid)
        result.append(parse_trigger(raw))
    return result


# =========================================================================
# Event Parser
# =========================================================================

def parse_event(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a single event record from event.get."""
    sev_int = _safe_int(raw.get("severity"), 0)
    return {
        "event_id": raw.get("eventid", ""),
        "object_id": raw.get("objectid", ""),
        "name": raw.get("name", ""),
        "severity": sev_int,
        "severity_label": PRIORITY_MAP.get(sev_int, "Not classified"),
        "severity_color": PRIORITY_COLOR.get(sev_int, "#94a3b8"),
        "value": _safe_int(raw.get("value"), 0),
        "acknowledged": raw.get("acknowledged") == "1",
        "clock": _parse_unix(raw.get("clock")),
        "clock_iso": _unix_to_iso(raw.get("clock")),
    }


def parse_events(raw_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [parse_event(r) for r in (raw_list or [])]


# =========================================================================
# Item / Metric Parser
# =========================================================================

def parse_item(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize an item record from item.get."""
    return {
        "item_id": raw.get("itemid", ""),
        "host_id": raw.get("hostid", ""),
        "name": raw.get("name", ""),
        "key": raw.get("key_", ""),
        "last_value": _safe_float(raw.get("lastvalue")),
        "units": raw.get("units", ""),
        "last_clock": _parse_unix(raw.get("lastclock")),
        "last_clock_iso": _unix_to_iso(raw.get("lastclock")),
        "status": "Enabled" if raw.get("status") == "0" else "Disabled",
    }


def parse_items(raw_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [parse_item(r) for r in (raw_list or [])]


# =========================================================================
# History Parser
# =========================================================================

def parse_history_point(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "item_id": raw.get("itemid", ""),
        "clock": _parse_unix(raw.get("clock")),
        "clock_iso": _unix_to_iso(raw.get("clock")),
        "value": _safe_float(raw.get("value")),
        "ns": _safe_int(raw.get("ns"), 0),
    }


def parse_history(raw_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [parse_history_point(r) for r in (raw_list or [])]


# =========================================================================
# Internal helpers
# =========================================================================

def _resolve_composite_availability(values: List[int]) -> int:
    """
    Compute aggregate availability code from multiple interface fields.

    Zabbix stores availability per interface type independently (agent,
    SNMP, IPMI, JMX). A host may be monitored by any combination of these.
    Values:
        0 = Unknown  (interface not configured or never polled)
        1 = Available
        2 = Unavailable

    Resolution logic:
        - If ANY interface reports 1 (Available)  → 1  (host is reachable)
        - Else if ANY reports 2 (Unavailable)     → 2  (host is down)
        - Otherwise all are 0                     → 0  (no active interfaces)
    """
    # Filter out interfaces that are not configured (value == 0 means
    # "not applicable" when the interface type is not in use).
    active = [v for v in values if v in (1, 2)]
    if not active:
        return 0   # all Unknown — no active interface configured
    if 1 in active:
        return 1   # at least one interface is up
    return 2       # all active interfaces are down


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
