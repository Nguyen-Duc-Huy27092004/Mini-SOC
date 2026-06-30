"""
Zabbix Host Diagnostics — Standalone Debug Tool
=================================================

PURPOSE
-------
Diagnose why hosts are not retrieved or incorrectly labelled by the Mini-SOC
Zabbix integration. For each host this script prints:
  - Raw fields returned by Zabbix API
  - What protocol was detected (and WHY — which step resolved it)
  - Availability resolution trace
  - Any parse errors

USAGE
-----
  # From project root:
  python -m backend.app.services.zabbix.zabbix_host_diagnostics

  # Or with explicit env vars:
  ZABBIX_API_URL=http://zabbix/api_jsonrpc.php \
  ZABBIX_API_USER=Admin \
  ZABBIX_API_PASSWORD=zabbix \
  python backend/app/services/zabbix/zabbix_host_diagnostics.py

  # Filter to specific hostid:
  python ... --host-id 10084

  # Export JSON report:
  python ... --output report.json

REQUIREMENTS
------------
  pip install aiohttp structlog
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Config — read from env (same as Mini-SOC settings)
# ---------------------------------------------------------------------------

ZABBIX_API_URL = os.environ.get("ZABBIX_API_URL", "http://localhost/api_jsonrpc.php")
ZABBIX_API_USER = os.environ.get("ZABBIX_API_USER", "Admin")
ZABBIX_API_PASSWORD = os.environ.get("ZABBIX_API_PASSWORD", "zabbix")

# ANSI colors
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_CYAN = "\033[36m"
_BOLD = "\033[1m"
_RESET = "\033[0m"


# ---------------------------------------------------------------------------
# Minimal async Zabbix client (no deps on app code)
# ---------------------------------------------------------------------------

async def _zabbix_call(session, url: str, method: str, params: dict, token: Optional[str]) -> Any:
    """Execute one JSON-RPC call, return result or raise."""
    payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with session.post(url, json=payload, headers=headers) as resp:
        body = await resp.json(content_type=None)
    if "error" in body:
        raise RuntimeError(f"Zabbix API error: {body['error']}")
    return body.get("result")


async def _authenticate(session, url: str, user: str, password: str) -> str:
    """Authenticate and return auth token (Zabbix 7.x Bearer style)."""
    token = await _zabbix_call(session, url, "user.login",
                               {"username": user, "password": password}, None)
    if not token:
        raise RuntimeError("Authentication failed — empty token")
    return token


async def _fetch_hosts(session, url: str, token: str) -> List[Dict[str, Any]]:
    """Fetch ALL monitored hosts with full interface / group / template data."""
    return await _zabbix_call(session, url, "host.get", {
        "output": [
            "hostid", "host", "name", "status",
            "available", "snmp_available", "ipmi_available", "jmx_available",
            "maintenance_status", "maintenance_from", "maintenance_type",
            "error", "description",
        ],
        "selectInterfaces": "extend",
        "selectGroups": "extend",
        "selectParentTemplates": ["name"],
        "filter": {"status": "0"},   # monitored only
    }, token)


# ---------------------------------------------------------------------------
# Protocol detection logic (mirrors zabbix_parser.py exactly)
# ---------------------------------------------------------------------------

def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


AVAILABILITY_MAP = {0: "Unknown", 1: "Available", 2: "Unavailable"}
HOST_STATUS_MAP  = {0: "Monitored", 1: "Not monitored"}


def _resolve_composite_availability(values: List[int]) -> int:
    active = [v for v in values if v in (1, 2)]
    if not active:
        return 0
    if 1 in active:
        return 1
    return 2


def _detect_protocol(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the 4-step protocol detection and return a full trace dict.
    
    Returns
    -------
    {
        "agent_types":    List[str],
        "available_code": int,
        "available_label": str,
        "ip_address":     Optional[str],
        "in_maintenance": bool,
        "trace":          List[str],   # human-readable step log
        "parse_error":    Optional[str],
    }
    """
    trace: List[str] = []
    try:
        status_int = _safe_int(raw.get("status"), 0)
        agent_types: set[str] = set()

        # ── Step 1: top-level availability fields ──────────────────────────
        top_level = {
            "agent": _safe_int(raw.get("available"),      0),
            "snmp":  _safe_int(raw.get("snmp_available"), 0),
            "ipmi":  _safe_int(raw.get("ipmi_available"), 0),
            "jmx":   _safe_int(raw.get("jmx_available"),  0),
        }
        avail_values: List[int] = list(top_level.values())
        step1_hits = []
        if top_level["agent"] != 0:
            agent_types.add("Zabbix Agent")
            step1_hits.append(f"available={top_level['agent']}")
        if top_level["snmp"] != 0:
            agent_types.add("SNMP")
            step1_hits.append(f"snmp_available={top_level['snmp']}")
        if top_level["ipmi"] != 0:
            agent_types.add("IPMI")
            step1_hits.append(f"ipmi_available={top_level['ipmi']}")
        if top_level["jmx"] != 0:
            agent_types.add("JMX")
            step1_hits.append(f"jmx_available={top_level['jmx']}")

        if step1_hits:
            trace.append(f"[Step 1 ✓] Top-level avail fields → {', '.join(step1_hits)}")
        else:
            trace.append("[Step 1 –] Top-level avail all zero")

        # ── Step 2: interface list ─────────────────────────────────────────
        interfaces = raw.get("interfaces") or []
        ip_address: Optional[str] = None
        step2_hits = []

        if isinstance(interfaces, list) and interfaces:
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
                iface_id = iface.get("interfaceid", "?")

                # Per-interface availability
                if "available" in iface:
                    ia = _safe_int(iface["available"], 0)
                    avail_values.append(ia)
                    avail_label = AVAILABILITY_MAP.get(ia, "?")
                    step2_hits.append(
                        f"iface#{iface_id} type={itype} available={ia}({avail_label})"
                    )
                else:
                    avail_values.append(0)
                    step2_hits.append(
                        f"iface#{iface_id} type={itype} available=MISSING(assumed Unknown)"
                    )

                proto_map = {1: "Zabbix Agent", 2: "SNMP", 3: "IPMI", 4: "JMX"}
                if itype in proto_map:
                    agent_types.add(proto_map[itype])

            trace.append(f"[Step 2 ✓] Interfaces ({len(interfaces)}) → {'; '.join(step2_hits)}")
        else:
            trace.append("[Step 2 –] No interfaces list returned")

        avail_int = _resolve_composite_availability(avail_values)
        trace.append(
            f"[Avail]    avail_values={avail_values} → composite={avail_int}"
            f" ({AVAILABILITY_MAP.get(avail_int, '?')})"
        )

        # ── Step 3: semantic override ──────────────────────────────────────
        groups = raw.get("groups") or raw.get("hostGroups") or []
        group_names = [g.get("name", "") for g in groups if isinstance(g, dict)]
        templates = raw.get("parentTemplates") or []
        template_names = [t.get("name", "") for t in templates if isinstance(t, dict)]

        semantic_types: set[str] = set()
        step3_hits = []
        for name in group_names + template_names:
            lower = name.lower()
            if "http agent" in lower or "dahua" in lower or "hikvision" in lower:
                semantic_types.add("HTTP Agent")
                step3_hits.append(f'"{name}"→HTTP Agent')
            elif "zabbix agent" in lower or "windows" in lower or "linux by zabbix" in lower:
                semantic_types.add("Zabbix Agent")
                step3_hits.append(f'"{name}"→Zabbix Agent')
            elif "snmp" in lower or "printer" in lower:
                semantic_types.add("SNMP")
                step3_hits.append(f'"{name}"→SNMP')
            elif "ipmi" in lower or "idrac" in lower or "ilo" in lower:
                semantic_types.add("IPMI")
                step3_hits.append(f'"{name}"→IPMI')
            elif "jmx" in lower:
                semantic_types.add("JMX")
                step3_hits.append(f'"{name}"→JMX')

        if semantic_types:
            trace.append(f"[Step 3 ✓] Semantic override: {'; '.join(step3_hits)}")
            trace.append(f"           Before={sorted(agent_types)} → After={sorted(semantic_types)}")
            agent_types = semantic_types
        else:
            trace.append(
                f"[Step 3 –] No semantic keywords in groups={group_names} "
                f"or templates={template_names}"
            )

        # ── Step 4: fallback ───────────────────────────────────────────────
        if not agent_types and status_int == 0:
            agent_types.add("HTTP Agent")
            trace.append("[Step 4 ✓] Fallback: no type detected → HTTP Agent")
            if avail_int == 0 and not raw.get("error"):
                avail_int = 1
                trace.append("[Step 4 ✓] HTTP Agent avail bumped: 0→1 (no error)")
        else:
            trace.append("[Step 4 –] Fallback not needed")

        # ── Maintenance ────────────────────────────────────────────────────
        maint_status = _safe_int(raw.get("maintenance_status"), 0)
        in_maintenance = maint_status == 1

        return {
            "agent_types":    sorted(agent_types),
            "available_code": avail_int,
            "available_label": AVAILABILITY_MAP.get(avail_int, "Unknown"),
            "ip_address":     ip_address,
            "in_maintenance": in_maintenance,
            "trace":          trace,
            "parse_error":    None,
        }

    except Exception as exc:
        return {
            "agent_types":    [],
            "available_code": 0,
            "available_label": "Unknown",
            "ip_address":     None,
            "in_maintenance": False,
            "trace":          trace,
            "parse_error":    str(exc),
        }


# ---------------------------------------------------------------------------
# Report printer
# ---------------------------------------------------------------------------

def _color(text: str, code: str) -> str:
    """Only color if stdout is a tty."""
    if sys.stdout.isatty():
        return f"{code}{text}{_RESET}"
    return text


def _avail_color(code: int) -> str:
    if code == 1:
        return _GREEN
    if code == 2:
        return _RED
    return _YELLOW


def print_host_report(raw: Dict[str, Any], result: Dict[str, Any], verbose: bool) -> None:
    host_id = raw.get("hostid", "?")
    name    = raw.get("name") or raw.get("host", "?")
    avail   = result["available_code"]
    label   = result["available_label"]
    protos  = result["agent_types"] or ["(none — UNRESOLVED)"]
    ip      = result["ip_address"] or "—"
    maint   = " [MAINTENANCE]" if result["in_maintenance"] else ""
    err     = raw.get("error", "") or ""
    perr    = result["parse_error"]

    print(_color(f"\n{'─'*70}", _CYAN))
    print(
        _color(f"Host: {name}", _BOLD)
        + f"  id={host_id}"
        + f"  ip={ip}"
        + maint
    )
    print(
        f"  Availability : {_color(label, _avail_color(avail))} (code={avail})"
    )
    print(f"  Protocol(s)  : {_color(', '.join(protos), _BOLD)}")

    if err:
        print(f"  Zabbix Error : {_color(err, _RED)}")
    if perr:
        print(f"  Parse Error  : {_color(perr, _RED)}")

    if verbose:
        print("  Detection trace:")
        for line in result["trace"]:
            marker = _GREEN if "✓" in line else (_YELLOW if "–" in line else "")
            print(f"    {_color(line, marker)}")

        # Show raw interface data
        interfaces = raw.get("interfaces") or []
        if interfaces:
            print(f"  Raw interfaces ({len(interfaces)}):")
            for iface in interfaces:
                itype = iface.get("type", "?")
                ia    = iface.get("available", "MISSING")
                print(
                    f"    interfaceid={iface.get('interfaceid','?')} "
                    f"type={itype} ip={iface.get('ip','?')} "
                    f"port={iface.get('port','?')} available={ia} "
                    f"main={iface.get('main','?')}"
                )

        # Show raw group + template names
        groups    = raw.get("groups") or []
        templates = raw.get("parentTemplates") or []
        if groups:
            gnames = [g.get("name", "?") for g in groups]
            print(f"  Groups    : {', '.join(gnames)}")
        if templates:
            tnames = [t.get("name", "?") for t in templates]
            print(f"  Templates : {', '.join(tnames)}")


# ---------------------------------------------------------------------------
# Summary statistics
# ---------------------------------------------------------------------------

def print_summary(hosts_raw: List[Dict], results: List[Dict]) -> None:
    from collections import Counter
    total = len(hosts_raw)
    avail_counter: Counter = Counter(r["available_code"] for r in results)
    proto_counter: Counter = Counter()
    for r in results:
        for p in (r["agent_types"] or ["UNRESOLVED"]):
            proto_counter[p] += 1
    parse_errors = sum(1 for r in results if r["parse_error"])
    unresolved   = sum(1 for r in results if not r["agent_types"])

    print(_color(f"\n{'═'*70}", _CYAN))
    print(_color(f"SUMMARY — {total} monitored hosts", _BOLD))
    print(f"  Available   : {_color(str(avail_counter[1]), _GREEN)}")
    print(f"  Unavailable : {_color(str(avail_counter[2]), _RED)}")
    print(f"  Unknown     : {_color(str(avail_counter[0]), _YELLOW)}")
    print()
    print("  Protocol breakdown:")
    for proto, count in proto_counter.most_common():
        bar = "█" * min(count, 40)
        color = _GREEN if proto != "UNRESOLVED" else _RED
        print(f"    {_color(proto, color):<20} {count:3d}  {bar}")
    if parse_errors:
        print(f"\n  {_color(f'Parse errors: {parse_errors}', _RED)}")
    if unresolved:
        print(f"  {_color(f'Unresolved protocol: {unresolved}', _YELLOW)}")
    print(_color("═"*70, _CYAN))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main(args: argparse.Namespace) -> None:
    try:
        import aiohttp
    except ImportError:
        print("ERROR: aiohttp not installed. Run: pip install aiohttp")
        sys.exit(1)

    api_url  = args.api_url  or ZABBIX_API_URL
    user     = args.user     or ZABBIX_API_USER
    password = args.password or ZABBIX_API_PASSWORD

    print(_color(f"Connecting to Zabbix API: {api_url}", _CYAN))

    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        # Authenticate
        try:
            token = await _authenticate(session, api_url, user, password)
            print(_color(f"  Authenticated ✓  (token: {token[:10]}...)", _GREEN))
        except Exception as exc:
            print(_color(f"  Authentication FAILED: {exc}", _RED))
            sys.exit(1)

        # Fetch hosts
        try:
            raw_hosts = await _fetch_hosts(session, api_url, token)
            print(_color(f"  Fetched {len(raw_hosts)} hosts ✓", _GREEN))
        except Exception as exc:
            print(_color(f"  host.get FAILED: {exc}", _RED))
            sys.exit(1)

    # Filter if --host-id specified
    if args.host_id:
        raw_hosts = [h for h in raw_hosts if h.get("hostid") == args.host_id]
        if not raw_hosts:
            print(_color(f"No host with hostid={args.host_id} found!", _RED))
            sys.exit(1)

    # Run detection on every host
    results: List[Dict] = []
    for raw in raw_hosts:
        result = _detect_protocol(raw)
        results.append(result)
        if not args.summary_only:
            print_host_report(raw, result, verbose=args.verbose)

    # Summary
    print_summary(raw_hosts, results)

    # Export JSON if requested
    if args.output:
        report = []
        for raw, res in zip(raw_hosts, results):
            report.append({
                "hostid":         raw.get("hostid"),
                "name":           raw.get("name") or raw.get("host"),
                "ip_address":     res["ip_address"],
                "agent_types":    res["agent_types"],
                "available_code": res["available_code"],
                "available_label": res["available_label"],
                "in_maintenance": res["in_maintenance"],
                "zabbix_error":   raw.get("error") or None,
                "parse_error":    res["parse_error"],
                "trace":          res["trace"],
                "raw_interfaces": raw.get("interfaces") or [],
                "groups":         [g.get("name") for g in (raw.get("groups") or [])],
                "templates":      [t.get("name") for t in (raw.get("parentTemplates") or [])],
            })
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\nJSON report written to: {_color(args.output, _GREEN)}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Diagnose Zabbix host fetch and protocol detection issues."
    )
    parser.add_argument("--api-url",  default=None, help="Zabbix API URL")
    parser.add_argument("--user",     default=None, help="Zabbix username")
    parser.add_argument("--password", default=None, help="Zabbix password")
    parser.add_argument("--host-id",  default=None, help="Filter to a specific hostid")
    parser.add_argument("--output",   default=None, help="Write JSON report to file")
    parser.add_argument("--verbose",  action="store_true", help="Show full detection trace")
    parser.add_argument("--summary-only", action="store_true",
                        help="Skip per-host output, show summary only")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(main(args))
