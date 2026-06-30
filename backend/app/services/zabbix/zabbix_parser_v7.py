"""
Zabbix 7.4 Data Parser

Professional data cleaning and normalization for Mini-SOC.
Converts raw Zabbix API responses into clean, human-readable data.

NEVER expose raw API responses to frontend.
All data must be parsed, cleaned, and validated.

Author: Principal Backend Engineer
Date: 2026-06-17
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)

# ================================================================
# Constants - Zabbix 7.4 Enums
# ================================================================

# Host status
HOST_STATUS = {
    0: "monitored",
    1: "not_monitored",
}

# Host availability
HOST_AVAILABILITY = {
    0: "unknown",
    1: "available",
    2: "unavailable",
}

# Interface availability field names for composite resolution
# (Zabbix stores each protocol's reachability independently)
_IFACE_AVAIL_FIELDS = [
    "available",      # Zabbix Agent (type 1)
    "snmp_available", # SNMP         (type 2)
    "ipmi_available", # IPMI         (type 3)
    "jmx_available",  # JMX          (type 4)
]

# IPMI availability
IPMI_AVAILABILITY = {
    0: "unknown",
    1: "available",
    2: "unavailable",
}

# Maintenance status
MAINTENANCE_STATUS = {
    0: "no_maintenance",
    1: "in_maintenance",
}

# Maintenance type
MAINTENANCE_TYPE = {
    0: "with_data_collection",
    1: "without_data_collection",
}

# Trigger severity
TRIGGER_SEVERITY = {
    0: "not_classified",
    1: "information",
    2: "warning",
    3: "average",
    4: "high",
    5: "disaster",
}

# Trigger severity colors for frontend
SEVERITY_COLORS = {
    0: "#97AAB3",  # Not classified - gray
    1: "#7499FF",  # Information - blue
    2: "#FFC859",  # Warning - yellow
    3: "#FFA059",  # Average - orange
    4: "#E97659",  # High - red
    5: "#E45959",  # Disaster - dark red
}

# Trigger priority (same as severity)
TRIGGER_PRIORITY = TRIGGER_SEVERITY

# Trigger status
TRIGGER_STATUS = {
    0: "enabled",
    1: "disabled",
}

# Trigger value
TRIGGER_VALUE = {
    0: "ok",
    1: "problem",
}

# Problem severity
PROBLEM_SEVERITY = TRIGGER_SEVERITY

# Event source
EVENT_SOURCE = {
    0: "trigger",
    1: "discovery",
    2: "auto_registration",
    3: "internal",
    4: "service",
}

# Event object
EVENT_OBJECT = {
    0: "trigger",
    1: "discovered_host",
    2: "discovered_service",
    3: "auto_registered_host",
    4: "item",
    5: "lldrule",
    6: "service",
}

# Event value
EVENT_VALUE = {
    0: "ok",
    1: "problem",
}

# Item value type
ITEM_VALUE_TYPE = {
    0: "float",
    1: "string",
    2: "log",
    3: "integer",
    4: "text",
}

# Item type
ITEM_TYPE = {
    0: "zabbix_agent",
    1: "snmp_v1",
    2: "zabbix_trapper",
    3: "simple_check",
    4: "snmp_v2",
    5: "zabbix_internal",
    6: "snmp_v3",
    7: "zabbix_agent_active",
    9: "web_item",
    10: "external_check",
    11: "database_monitor",
    12: "ipmi_agent",
    13: "ssh_agent",
    14: "telnet_agent",
    15: "calculated",
    16: "jmx_agent",
    17: "snmp_trap",
    18: "dependent_item",
    19: "http_agent",
    20: "snmp_agent",
    21: "script",
}

# Item status
ITEM_STATUS = {
    0: "enabled",
    1: "disabled",
}

# Item state
ITEM_STATE = {
    0: "normal",
    1: "not_supported",
}


# ================================================================
# Timestamp Conversion
# ================================================================

def parse_timestamp(timestamp: Any) -> Optional[str]:
    """
    Convert Unix timestamp to ISO 8601 format.
    
    Args:
        timestamp: Unix timestamp (int or string)
        
    Returns:
        ISO 8601 formatted datetime string or None
    """
    try:
        if timestamp is None or timestamp == "" or timestamp == "0":
            return None
        
        ts = int(timestamp)
        if ts <= 0:
            return None
        
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        return dt.isoformat()
    except (ValueError, TypeError, OSError):
        logger.warning("parse_timestamp_failed", timestamp=timestamp)
        return None


def parse_timestamp_human(timestamp: Any) -> Optional[str]:
    """
    Convert Unix timestamp to human-readable format.
    
    Returns: "2026-06-17 10:30:45 UTC"
    """
    try:
        if timestamp is None or timestamp == "" or timestamp == "0":
            return None
        
        ts = int(timestamp)
        if ts <= 0:
            return None
        
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, TypeError, OSError):
        logger.warning("parse_timestamp_human_failed", timestamp=timestamp)
        return None


def get_time_ago(timestamp: Any) -> Optional[str]:
    """
    Convert timestamp to relative time.
    
    Returns: "5 minutes ago", "2 hours ago", "3 days ago"
    """
    try:
        if timestamp is None or timestamp == "" or timestamp == "0":
            return None
        
        ts = int(timestamp)
        if ts <= 0:
            return None
        
        now = datetime.now(tz=timezone.utc)
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        delta = now - dt
        
        seconds = delta.total_seconds()
        
        if seconds < 60:
            return f"{int(seconds)} seconds ago"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        else:
            days = int(seconds / 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"
            
    except (ValueError, TypeError, OSError):
        return None


# ================================================================
# Host Parsing
# ================================================================

def parse_host(host: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse and clean host data.
    
    Removes null values, converts timestamps, and adds human-readable fields.

    Agent type detection strategy (same as zabbix_parser.py):
      1. Read top-level available/snmp_available/ipmi_available/jmx_available
      2. Then read interface.type from selectInterfaces list
      3. Fallback: host has no interface → HTTP Agent / internal checks
    """
    try:
        # Basic info
        parsed = {
            "hostid": host.get("hostid", ""),
            "host": host.get("host", ""),
            "name": host.get("name", host.get("host", "")),
            "description": host.get("description", ""),
        }
        
        # Status fields with human-readable values
        status_raw = int(host.get("status", 0))
        parsed["status"] = HOST_STATUS.get(status_raw, "unknown")
        parsed["status_code"] = status_raw
        parsed["monitored"] = status_raw == 0

        # ── Step 1: top-level availability fields (all Zabbix versions) ──────
        top_level_avail = {
            "agent": int(host.get("available", 0)),
            "snmp":  int(host.get("snmp_available", 0)),
            "ipmi":  int(host.get("ipmi_available", 0)),
            "jmx":   int(host.get("jmx_available", 0)),
        }
        avail_values = list(top_level_avail.values())
        agent_types: set[str] = set()

        if top_level_avail["agent"] != 0:
            agent_types.add("Zabbix Agent")
        if top_level_avail["snmp"] != 0:
            agent_types.add("SNMP")
        if top_level_avail["ipmi"] != 0:
            agent_types.add("IPMI")
        if top_level_avail["jmx"] != 0:
            agent_types.add("JMX")

        # Compute preliminary availability
        available_raw = _resolve_composite_availability(avail_values)
        
        # Maintenance
        maintenance_raw = int(host.get("maintenance_status", 0))
        parsed["maintenance_status"] = MAINTENANCE_STATUS.get(maintenance_raw, "unknown")
        parsed["in_maintenance"] = maintenance_raw == 1
        
        if maintenance_raw == 1:
            parsed["maintenance_from"] = parse_timestamp(host.get("maintenance_from"))
            parsed["maintenance_type"] = MAINTENANCE_TYPE.get(
                int(host.get("maintenance_type", 0)),
                "unknown"
            )
        
        # Error info
        error = host.get("error", "")
        if error:
            parsed["error"] = error
        
        # Counts
        items_num = host.get("items_num")
        if items_num is not None:
            parsed["items_count"] = int(items_num)
        
        # Groups
        if "groups" in host and isinstance(host["groups"], list):
            parsed["groups"] = [
                {
                    "groupid": g.get("groupid", ""),
                    "name": g.get("name", ""),
                }
                for g in host["groups"]
            ]
        
        # ── Step 2: Interfaces (Zabbix >= 6.4 moves avail into interfaces) ──
        if "interfaces" in host and isinstance(host["interfaces"], list) and host["interfaces"]:
            iface_list = host["interfaces"]
            parsed["interfaces"] = []
            for iface in iface_list:
                if not isinstance(iface, dict):
                    continue
                itype = int(iface.get("type", 1))
                parsed["interfaces"].append({
                    "interfaceid": iface.get("interfaceid", ""),
                    "ip": iface.get("ip", ""),
                    "dns": iface.get("dns", ""),
                    "port": iface.get("port", ""),
                    "type": itype,
                    "main": bool(int(iface.get("main", 0))),
                })
                # Interface-level availability (Zabbix >= 6.4)
                if "available" in iface:
                    avail_values.append(int(iface.get("available", 0)))
                # Classify agent type from interface type
                if itype == 1:
                    agent_types.add("Zabbix Agent")
                elif itype == 2:
                    agent_types.add("SNMP")
                elif itype == 3:
                    agent_types.add("IPMI")
                elif itype == 4:
                    agent_types.add("JMX")

            # Recompute availability now that interface-level values are added
            available_raw = _resolve_composite_availability(avail_values)
            
        # ── Step 3: Semantic override based on user-defined groups and templates
        # This solves the issue where Zabbix Active Agents have no interfaces, 
        # or HTTP Agents use dummy Zabbix Agent interfaces.
        templates = host.get("parentTemplates") or []
        template_names = [t.get("name", "") for t in templates if isinstance(t, dict)]
        group_names = [g["name"] for g in parsed.get("groups", [])]
        
        semantic_types: set[str] = set()
        for name in group_names + template_names:
            lower_name = name.lower()
            if "http agent" in lower_name or "dahua" in lower_name or "hikvision" in lower_name:
                semantic_types.add("HTTP Agent")
            elif "zabbix agent" in lower_name or "windows" in lower_name or "linux by zabbix" in lower_name:
                semantic_types.add("Zabbix Agent")
            elif "snmp" in lower_name or "printer" in lower_name:
                semantic_types.add("SNMP")
                
        if semantic_types:
            agent_types = semantic_types

        # ── Step 4: Fallback — no interface = HTTP Agent / internal ──────────
        if not agent_types and status_raw == 0:
            agent_types.add("HTTP Agent")
            # HTTP Agent availability is determined by items, not interfaces.
            # If all values are Unknown (0) and no error, assume Available.
            if available_raw == 0 and not parsed.get("error"):
                available_raw = 1

        parsed["availability"] = HOST_AVAILABILITY.get(available_raw, "unknown")
        parsed["availability_code"] = available_raw
        parsed["is_available"] = available_raw == 1
        parsed["agent_types"] = sorted(agent_types)

        # IPMI availability (kept for backward compat)
        ipmi_raw = int(host.get("ipmi_available", 0))
        parsed["ipmi_availability"] = IPMI_AVAILABILITY.get(ipmi_raw, "unknown")
        
        # Remove None values
        return {k: v for k, v in parsed.items() if v is not None and v != ""}
        
    except Exception as exc:
        logger.error("parse_host_failed", error=str(exc), host_id=host.get("hostid"))
        return {}


def parse_host_list(hosts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Parse list of hosts, filtering out failures."""
    parsed = []
    for host in hosts:
        parsed_host = parse_host(host)
        if parsed_host:
            parsed.append(parsed_host)
    return parsed


# ================================================================
# Problem Parsing
# ================================================================

def parse_problem(problem: Dict[str, Any]) -> Dict[str, Any]:
    """Parse and clean problem data."""
    try:
        parsed = {
            "eventid": problem.get("eventid", ""),
            "objectid": problem.get("objectid", ""),
            "name": problem.get("name", ""),
            "clock": parse_timestamp(problem.get("clock")),
            "clock_human": parse_timestamp_human(problem.get("clock")),
            "time_ago": get_time_ago(problem.get("clock")),
        }
        
        # Severity
        severity_raw = int(problem.get("severity", 0))
        parsed["severity"] = PROBLEM_SEVERITY.get(severity_raw, "unknown")
        parsed["severity_code"] = severity_raw
        parsed["severity_color"] = SEVERITY_COLORS.get(severity_raw, "#97AAB3")
        
        # Status flags
        parsed["acknowledged"] = bool(int(problem.get("acknowledged", 0)))
        parsed["suppressed"] = bool(int(problem.get("suppressed", 0)))
        
        # Operational data
        opdata = problem.get("opdata", "")
        if opdata:
            parsed["operational_data"] = opdata
        
        # URLs
        urls = problem.get("urls", [])
        if urls:
            parsed["urls"] = urls
        
        # Recovery event
        r_eventid = problem.get("r_eventid", "0")
        if r_eventid != "0":
            parsed["recovered"] = True
            parsed["recovery_eventid"] = r_eventid
        else:
            parsed["recovered"] = False
        
        # Acknowledges
        if "acknowledges" in problem and isinstance(problem["acknowledges"], list):
            parsed["acknowledges"] = [
                {
                    "acknowledgeid": ack.get("acknowledgeid", ""),
                    "userid": ack.get("userid", ""),
                    "message": ack.get("message", ""),
                    "clock": parse_timestamp(ack.get("clock")),
                    "action": int(ack.get("action", 0)),
                }
                for ack in problem["acknowledges"]
            ]
        
        # Tags
        if "tags" in problem and isinstance(problem["tags"], list):
            parsed["tags"] = [
                {
                    "tag": tag.get("tag", ""),
                    "value": tag.get("value", ""),
                }
                for tag in problem["tags"]
            ]
        
        return {k: v for k, v in parsed.items() if v is not None and v != ""}
        
    except Exception as exc:
        logger.error("parse_problem_failed", error=str(exc))
        return {}


def parse_problem_list(problems: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Parse list of problems."""
    parsed = []
    for problem in problems:
        parsed_problem = parse_problem(problem)
        if parsed_problem:
            parsed.append(parsed_problem)
    return parsed


# ================================================================
# Trigger Parsing
# ================================================================

def parse_trigger(trigger: Dict[str, Any]) -> Dict[str, Any]:
    """Parse and clean trigger data."""
    try:
        parsed = {
            "triggerid": trigger.get("triggerid", ""),
            "description": trigger.get("description", ""),
            "expression": trigger.get("expression", ""),
        }
        
        # Priority (severity)
        priority_raw = int(trigger.get("priority", 0))
        parsed["priority"] = TRIGGER_PRIORITY.get(priority_raw, "unknown")
        parsed["priority_code"] = priority_raw
        parsed["severity_color"] = SEVERITY_COLORS.get(priority_raw, "#97AAB3")
        
        # Status
        status_raw = int(trigger.get("status", 0))
        parsed["status"] = TRIGGER_STATUS.get(status_raw, "unknown")
        parsed["enabled"] = status_raw == 0
        
        # Value (current state)
        value_raw = int(trigger.get("value", 0))
        parsed["value"] = TRIGGER_VALUE.get(value_raw, "unknown")
        parsed["is_problem"] = value_raw == 1
        
        # Last change
        parsed["lastchange"] = parse_timestamp(trigger.get("lastchange"))
        parsed["lastchange_human"] = parse_timestamp_human(trigger.get("lastchange"))
        parsed["lastchange_ago"] = get_time_ago(trigger.get("lastchange"))
        
        # Error
        error = trigger.get("error", "")
        if error:
            parsed["error"] = error
        
        # Operational data
        opdata = trigger.get("opdata", "")
        if opdata:
            parsed["operational_data"] = opdata
        
        # URL
        url = trigger.get("url", "")
        if url:
            parsed["url"] = url
        
        # Recovery mode
        recovery_mode = trigger.get("recovery_mode")
        if recovery_mode is not None:
            parsed["recovery_mode"] = int(recovery_mode)
        
        # Manual close
        manual_close = trigger.get("manual_close")
        if manual_close is not None:
            parsed["manual_close"] = bool(int(manual_close))
        
        # Hosts
        if "hosts" in trigger and isinstance(trigger["hosts"], list):
            parsed["hosts"] = [
                {
                    "hostid": h.get("hostid", ""),
                    "host": h.get("host", ""),
                    "name": h.get("name", ""),
                }
                for h in trigger["hosts"]
            ]
        
        return {k: v for k, v in parsed.items() if v is not None and v != ""}
        
    except Exception as exc:
        logger.error("parse_trigger_failed", error=str(exc))
        return {}


def parse_trigger_list(triggers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Parse list of triggers."""
    parsed = []
    for trigger in triggers:
        parsed_trigger = parse_trigger(trigger)
        if parsed_trigger:
            parsed.append(parsed_trigger)
    return parsed


# ================================================================
# Event Parsing
# ================================================================

def parse_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Parse and clean event data."""
    try:
        parsed = {
            "eventid": event.get("eventid", ""),
            "name": event.get("name", ""),
            "clock": parse_timestamp(event.get("clock")),
            "clock_human": parse_timestamp_human(event.get("clock")),
            "time_ago": get_time_ago(event.get("clock")),
        }
        
        # Source
        source_raw = int(event.get("source", 0))
        parsed["source"] = EVENT_SOURCE.get(source_raw, "unknown")
        
        # Object
        object_raw = int(event.get("object", 0))
        parsed["object"] = EVENT_OBJECT.get(object_raw, "unknown")
        parsed["objectid"] = event.get("objectid", "")
        
        # Value
        value_raw = int(event.get("value", 0))
        parsed["value"] = EVENT_VALUE.get(value_raw, "unknown")
        parsed["is_problem"] = value_raw == 1
        
        # Severity
        severity_raw = int(event.get("severity", 0))
        if severity_raw > 0:
            parsed["severity"] = PROBLEM_SEVERITY.get(severity_raw, "unknown")
            parsed["severity_code"] = severity_raw
            parsed["severity_color"] = SEVERITY_COLORS.get(severity_raw, "#97AAB3")
        
        # Flags
        parsed["acknowledged"] = bool(int(event.get("acknowledged", 0)))
        suppressed = event.get("suppressed")
        if suppressed is not None:
            parsed["suppressed"] = bool(int(suppressed))
        
        # Recovery
        r_eventid = event.get("r_eventid", "0")
        if r_eventid != "0":
            parsed["recovery_eventid"] = r_eventid
        
        return {k: v for k, v in parsed.items() if v is not None and v != ""}
        
    except Exception as exc:
        logger.error("parse_event_failed", error=str(exc))
        return {}


def parse_event_list(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Parse list of events."""
    parsed = []
    for event in events:
        parsed_event = parse_event(event)
        if parsed_event:
            parsed.append(parsed_event)
    return parsed


# ================================================================
# Item Parsing
# ================================================================

def parse_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Parse and clean item data."""
    try:
        parsed = {
            "itemid": item.get("itemid", ""),
            "hostid": item.get("hostid", ""),
            "name": item.get("name", ""),
            "key": item.get("key_", ""),
        }
        
        # Type
        type_raw = int(item.get("type", 0))
        parsed["type"] = ITEM_TYPE.get(type_raw, "unknown")
        
        # Value type
        value_type_raw = int(item.get("value_type", 0))
        parsed["value_type"] = ITEM_VALUE_TYPE.get(value_type_raw, "unknown")
        
        # Status
        status_raw = int(item.get("status", 0))
        parsed["status"] = ITEM_STATUS.get(status_raw, "unknown")
        parsed["enabled"] = status_raw == 0
        
        # State
        state_raw = int(item.get("state", 0))
        parsed["state"] = ITEM_STATE.get(state_raw, "unknown")
        parsed["supported"] = state_raw == 0
        
        # Values
        lastvalue = item.get("lastvalue")
        if lastvalue not in (None, ""):
            parsed["lastvalue"] = lastvalue
        
        prevvalue = item.get("prevvalue")
        if prevvalue not in (None, ""):
            parsed["prevvalue"] = prevvalue
        
        # Units
        units = item.get("units", "")
        if units:
            parsed["units"] = units
        
        # Timestamps
        lastclock = item.get("lastclock")
        if lastclock:
            parsed["lastclock"] = parse_timestamp(lastclock)
            parsed["lastclock_human"] = parse_timestamp_human(lastclock)
        
        # Error
        error = item.get("error", "")
        if error:
            parsed["error"] = error
        
        return {k: v for k, v in parsed.items() if v is not None and v != ""}
        
    except Exception as exc:
        logger.error("parse_item_failed", error=str(exc))
        return {}


def parse_item_list(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Parse list of items."""
    parsed = []
    for item in items:
        parsed_item = parse_item(item)
        if parsed_item:
            parsed.append(parsed_item)
    return parsed


# ================================================================
# History Parsing
# ================================================================

def parse_history(history: Dict[str, Any]) -> Dict[str, Any]:
    """Parse history point."""
    try:
        parsed = {
            "itemid": history.get("itemid", ""),
            "clock": parse_timestamp(history.get("clock")),
            "value": history.get("value", ""),
        }
        
        # Nanoseconds if available
        ns = history.get("ns")
        if ns:
            parsed["ns"] = ns
        
        return {k: v for k, v in parsed.items() if v is not None and v != ""}
        
    except Exception as exc:
        logger.error("parse_history_failed", error=str(exc))
        return {}


def parse_history_list(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Parse list of history points."""
    parsed = []
    for point in history:
        parsed_point = parse_history(point)
        if parsed_point:
            parsed.append(parsed_point)
    return parsed


# ================================================================
# Maintenance Parsing
# ================================================================

def parse_maintenance(maintenance: Dict[str, Any]) -> Dict[str, Any]:
    """Parse maintenance schedule."""
    try:
        parsed = {
            "maintenanceid": maintenance.get("maintenanceid", ""),
            "name": maintenance.get("name", ""),
            "description": maintenance.get("description", ""),
        }
        
        # Type
        type_raw = int(maintenance.get("maintenance_type", 0))
        parsed["maintenance_type"] = MAINTENANCE_TYPE.get(type_raw, "unknown")
        
        # Time period
        parsed["active_since"] = parse_timestamp(maintenance.get("active_since"))
        parsed["active_since_human"] = parse_timestamp_human(maintenance.get("active_since"))
        parsed["active_till"] = parse_timestamp(maintenance.get("active_till"))
        parsed["active_till_human"] = parse_timestamp_human(maintenance.get("active_till"))
        
        return {k: v for k, v in parsed.items() if v is not None and v != ""}
        
    except Exception as exc:
        logger.error("parse_maintenance_failed", error=str(exc))
        return {}


def parse_maintenance_list(maintenances: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Parse list of maintenance schedules."""
    parsed = []
    for maint in maintenances:
        parsed_maint = parse_maintenance(maint)
        if parsed_maint:
            parsed.append(parsed_maint)
    return parsed


# ================================================================
# Composite Availability Helper
# ================================================================

def _resolve_composite_availability(values: List[int]) -> int:
    """
    Compute aggregate availability from multiple Zabbix interface fields.

    Zabbix stores reachability separately per interface protocol:
        available      -> Agent (type 1)
        snmp_available -> SNMP  (type 2)
        ipmi_available -> IPMI  (type 3)
        jmx_available  -> JMX   (type 4)

    Each field encodes:
        0 = Unknown  (interface not configured or never checked)
        1 = Available
        2 = Unavailable

    Resolution priority (matches Zabbix web UI logic):
        ANY interface == 1  ->  1  (Available  — host is reachable)
        ALL active   == 2   ->  2  (Unavailable — host is down)
        All          == 0   ->  0  (Unknown     — no active interfaces)
    """
    active = [v for v in values if v in (1, 2)]
    if not active:
        return 0   # no interface configured / never polled
    if 1 in active:
        return 1   # at least one interface is up
    return 2       # all active interfaces are down

