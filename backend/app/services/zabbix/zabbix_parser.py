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
    """Normalize a single host record from host.get.

    Agent type detection strategy (4-step priority):
      1. Top-level availability fields (available/snmp_available/ipmi_available/jmx_available)
         → always present in all Zabbix versions, used as baseline.
      2. Interface list (selectInterfaces=extend): read interface.type.
         In Zabbix ≥ 6.4 each interface also carries its own `available` field;
         in older versions we infer availability from whether the interface exists.
      3. Semantic override: group names + template names contain keywords like
         "HTTP Agent", "SNMP", "Windows", etc. — these take precedence over raw
         interface types because the admin explicitly tagged the host.
      4. Fallback: monitored host with no detected type → HTTP Agent / internal check.
    """
    try:
        status_int = _safe_int(raw.get("status"), 0)

        # ── Step 1: top-level availability fields ────────────────────────────
        # These fields exist in ALL Zabbix versions and tell us which protocol
        # interfaces were at least attempted.  0=unknown, 1=available, 2=unavail.
        top_level_avail = {
            "agent": _safe_int(raw.get("available"),      0),
            "snmp":  _safe_int(raw.get("snmp_available"), 0),
            "ipmi":  _safe_int(raw.get("ipmi_available"), 0),
            "jmx":   _safe_int(raw.get("jmx_available"),  0),
        }
        avail_values: List[int] = list(top_level_avail.values())
        agent_types: set[str] = set()

        if top_level_avail["agent"] != 0:
            agent_types.add("Zabbix Agent")
        if top_level_avail["snmp"] != 0:
            agent_types.add("SNMP")
        if top_level_avail["ipmi"] != 0:
            agent_types.add("IPMI")
        if top_level_avail["jmx"] != 0:
            agent_types.add("JMX")

        # ── Step 2: interface list ────────────────────────────────────────────
        interfaces = raw.get("interfaces") or []
        ip_address: Optional[str] = None

        if isinstance(interfaces, list) and interfaces:
            # Primary IP: prefer interface marked main=1, else use first
            primary = next(
                (i for i in interfaces
                 if isinstance(i, dict) and i.get("main") in ("1", 1, True)),
                interfaces[0]
            )
            ip_address = primary.get("ip") or primary.get("dns") or None

            for iface in interfaces:
                if not isinstance(iface, dict):
                    continue

                itype = _safe_int(iface.get("type"), 0)

                # Interface-level availability (Zabbix ≥ 6.4).
                # If the field is absent (older Zabbix), we still know the
                # protocol from itype — treat it as "configured" (unknown avail).
                if "available" in iface:
                    avail_values.append(_safe_int(iface["available"], 0))
                else:
                    # Interface exists but no per-interface avail → mark as
                    # unknown (0) so it doesn't incorrectly block availability.
                    avail_values.append(0)

                if itype == 1:
                    agent_types.add("Zabbix Agent")
                elif itype == 2:
                    agent_types.add("SNMP")
                elif itype == 3:
                    agent_types.add("IPMI")
                elif itype == 4:
                    agent_types.add("JMX")

        avail_int = _resolve_composite_availability(avail_values)

        # ── Step 3: semantic override via groups + templates ──────────────────
        groups = raw.get("groups") or raw.get("hostGroups") or []
        group_names = [g.get("name", "") for g in groups if isinstance(g, dict)]

        templates = raw.get("parentTemplates") or []
        template_names = [t.get("name", "") for t in templates if isinstance(t, dict)]

        semantic_types: set[str] = set()
        for name in group_names + template_names:
            lower = name.lower()
            if "http agent" in lower or "dahua" in lower or "hikvision" in lower:
                semantic_types.add("HTTP Agent")
            elif (
                "zabbix agent" in lower
                or "windows" in lower
                or "linux by zabbix" in lower
            ):
                semantic_types.add("Zabbix Agent")
            elif "snmp" in lower or "printer" in lower:
                semantic_types.add("SNMP")
            elif "ipmi" in lower or "idrac" in lower or "ilo" in lower:
                semantic_types.add("IPMI")
            elif "jmx" in lower:
                semantic_types.add("JMX")

        if semantic_types:
            agent_types = semantic_types

        # ── Step 4: fallback ─────────────────────────────────────────────────
        if not agent_types and status_int == 0:
            agent_types.add("HTTP Agent")
            # HTTP Agent hosts track availability via item state, not interfaces.
            # If all avail codes are 0 (unknown) and no error → assume available.
            if avail_int == 0 and not raw.get("error"):
                avail_int = 1

        # ── Maintenance ───────────────────────────────────────────────────────
        maintenance_status = _safe_int(raw.get("maintenance_status"), 0)
        in_maintenance = maintenance_status == 1

        return {
            "host_id":        raw.get("hostid", ""),
            "name":           raw.get("name") or raw.get("host", ""),
            "hostname":       raw.get("host", ""),
            "status":         HOST_STATUS_MAP.get(status_int, "Unknown"),
            "status_code":    status_int,
            "available":      avail_int == 1,
            "available_label": AVAILABILITY_MAP.get(avail_int, "Unknown"),
            "available_code": avail_int,
            "ip_address":     ip_address,
            "groups":         group_names,
            "agent_types":    sorted(agent_types),
            "error":          raw.get("error") or None,
            "in_maintenance": in_maintenance,
            "description":    raw.get("description") or None,
        }

    except Exception as exc:
        import structlog as _sl
        _sl.get_logger().error(
            "parse_host_failed",
            host_id=raw.get("hostid"),
            error=str(exc),
        )
        return {}


def parse_hosts(raw_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize a list of hosts, removing duplicates by host_id.

    Hosts that fail to parse (return {}) are silently dropped so that a
    single malformed record never crashes the entire host list.
    """
    seen: set[str] = set()
    result = []
    for raw in (raw_list or []):
        host_id = raw.get("hostid", "")
        if not host_id or host_id in seen:
            continue
        seen.add(host_id)
        parsed = parse_host(raw)
        if parsed:  # skip empty-dict failures
            result.append(parsed)
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
        "item_id":       raw.get("itemid", ""),
        "host_id":       raw.get("hostid", ""),
        "name":          raw.get("name", ""),
        "key":           raw.get("key_", ""),
        "last_value":    _safe_float(raw.get("lastvalue")),
        "units":         raw.get("units", ""),
        "last_clock":    _parse_unix(raw.get("lastclock")),
        "last_clock_iso": _unix_to_iso(raw.get("lastclock")),
        "status":        "Enabled" if raw.get("status") == "0" else "Disabled",
        # state: 0=normal (collecting), 1=not_supported (broken)
        # This is the primary availability signal for HTTP Agent hosts
        "state":         _safe_int(raw.get("state"), 0),
        "state_label":   "normal" if _safe_int(raw.get("state"), 0) == 0 else "not_supported",
        # item type: 0=zabbix_agent, 7=active_agent, 19=http_agent, etc.
        "type":          _safe_int(raw.get("type"), 0),
        "error":         raw.get("error") or None,
    }


def parse_items(raw_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [parse_item(r) for r in (raw_list or [])]


# =========================================================================
# HTTP Agent / Active Agent Availability Resolution
# =========================================================================

# Item types that indicate HTTP Agent or Zabbix Active Agent monitoring
_HTTP_AGENT_ITEM_TYPES  = {19}      # type 19 = http_agent
_ACTIVE_AGENT_ITEM_TYPES = {7}      # type 7  = zabbix_agent_active


def resolve_http_agent_availability(items: List[Dict[str, Any]], host_ids: set) -> Dict[str, int]:
    """
    For hosts that have no real interfaces (HTTP Agent, Active Agent),
    infer availability from item state.

    Logic:
      - If ANY item for this host has state=0 (normal/collecting) → Available (1)
      - If ALL items are state=1 (not_supported) → Unavailable (2)
      - If NO items exist for this host → Unknown (0)

    Returns: Dict[host_id → availability_code]
    """
    # Group items by host_id
    host_item_states: Dict[str, List[int]] = {}
    for item in items:
        hid = item.get("host_id", "")
        if hid not in host_ids:
            continue
        state = item.get("state", 0)  # 0=normal, 1=not_supported
        host_item_states.setdefault(hid, []).append(state)

    result: Dict[str, int] = {}
    for hid in host_ids:
        states = host_item_states.get(hid, [])
        if not states:
            result[hid] = 0  # Unknown — no items at all
        elif 0 in states:
            result[hid] = 1  # Available — at least one item is collecting
        else:
            result[hid] = 2  # Unavailable — all items are not_supported
    return result


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
