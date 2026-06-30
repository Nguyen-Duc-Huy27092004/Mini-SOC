"""
Zabbix API Client (async JSON-RPC).

Implements all required Zabbix API methods:
  - host.get
  - hostgroup.get
  - item.get
  - trigger.get
  - problem.get
  - event.get
  - history.get

Features:
  - Async aiohttp session with connection pooling
  - Auth token injection via ZabbixAuthManager
  - Retry with exponential backoff (3 attempts)
  - 30s request timeout
  - 401 / auth failure → auto-invalidate + re-authenticate
  - Structured logging of every request + response
  - Returns [] / None on all failure paths (never raises)
"""
from __future__ import annotations

import asyncio
import ssl
import time
from typing import Any, Dict, List, Optional

import aiohttp
import structlog

from app.services.zabbix.zabbix_auth import ZabbixAuthManager

logger = structlog.get_logger()

_MAX_RETRIES = 3
_BACKOFF_BASE = 1.5  # seconds
_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30, connect=10, sock_read=25)
_RPC_ID_COUNTER = 0


def _next_rpc_id() -> int:
    global _RPC_ID_COUNTER
    _RPC_ID_COUNTER = (_RPC_ID_COUNTER + 1) % 100_000
    return _RPC_ID_COUNTER


class ZabbixClient:
    """
    Production-grade async Zabbix JSON-RPC client.

    All public methods return normalized Python objects.
    On error, they return empty list [] or None — never raise.
    """

    def __init__(
        self,
        api_url: str,
        user: str,
        password: str,
        verify_ssl: bool = True,
        timeout: int = 30,
    ) -> None:
        self.api_url = api_url
        self._auth = ZabbixAuthManager(api_url, user, password)
        self._verify_ssl = verify_ssl
        self._timeout = aiohttp.ClientTimeout(total=timeout, connect=10)
        self._session: Optional[aiohttp.ClientSession] = None

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session and not self._session.closed:
            return self._session

        if self._verify_ssl:
            ssl_ctx: bool | ssl.SSLContext = True
        else:
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE

        connector = aiohttp.TCPConnector(ssl=ssl_ctx, limit=10, ttl_dns_cache=300)
        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=self._timeout,
            headers={"Content-Type": "application/json"},
            raise_for_status=False,
        )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            logger.info("zabbix_client_closed")

    # ------------------------------------------------------------------
    # Core JSON-RPC request
    # ------------------------------------------------------------------

    async def _call(
        self,
        method: str,
        params: Dict[str, Any],
        retry_count: int = 0,
    ) -> Optional[Any]:
        """Execute a single JSON-RPC call with retry + auth refresh."""
        session = await self._get_session()
        token = await self._auth.get_token(session)

        if token is None:
            logger.error("zabbix_call_no_token", method=method)
            return None

        payload: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": _next_rpc_id(),
        }

        start = time.monotonic()
        logger.debug("zabbix_request", method=method, url=self.api_url)

        try:
            # For Zabbix 7.4+, we pass the auth token in the headers
            headers = {"Authorization": f"Bearer {token}"}
            async with session.post(self.api_url, json=payload, headers=headers) as resp:
                latency = round(time.monotonic() - start, 3)
                status_code = resp.status
                body_text = await resp.text()

                logger.debug(
                    "zabbix_response",
                    method=method,
                    status=status_code,
                    latency=latency,
                    body_preview=body_text[:200],
                )

                if status_code == 200:
                    try:
                        body = await resp.json(content_type=None)
                    except Exception:
                        import json
                        body = json.loads(body_text)

                    if "error" in body:
                        err = body["error"]
                        # Auth error → invalidate token and retry once
                        if err.get("code") in (-32602, -32600) or "re-login" in str(err.get("data", "")):
                            if retry_count < 1:
                                await self._auth.invalidate()
                                logger.warning(
                                    "zabbix_auth_error_retrying",
                                    method=method,
                                    error=err,
                                )
                                return await self._call(method, params, retry_count + 1)
                        logger.error(
                            "zabbix_api_error",
                            method=method,
                            code=err.get("code"),
                            data=str(err.get("data", ""))[:200],
                        )
                        return None

                    return body.get("result")

                # HTTP-level errors → retry with backoff
                if status_code in (429, 500, 502, 503, 504) and retry_count < _MAX_RETRIES:
                    backoff = _BACKOFF_BASE ** retry_count
                    logger.warning(
                        "zabbix_request_retrying",
                        method=method,
                        status=status_code,
                        retry=retry_count + 1,
                        backoff=backoff,
                    )
                    await asyncio.sleep(backoff)
                    return await self._call(method, params, retry_count + 1)

                logger.error(
                    "zabbix_request_failed",
                    method=method,
                    status=status_code,
                    body_preview=body_text[:300],
                )
                return None

        except asyncio.TimeoutError:
            logger.warning("zabbix_request_timeout", method=method)
            if retry_count < _MAX_RETRIES:
                await asyncio.sleep(_BACKOFF_BASE ** retry_count)
                return await self._call(method, params, retry_count + 1)
            return None

        except aiohttp.ClientError as exc:
            logger.error("zabbix_client_error", method=method, error=str(exc))
            return None

        except Exception as exc:
            logger.exception("zabbix_request_exception", method=method, error=str(exc))
            return None

    # ------------------------------------------------------------------
    # Public API Methods
    # ------------------------------------------------------------------

    async def host_get(
        self,
        *,
        output: List[str] = None,
        selectGroups: str = "extend",
        selectInterfaces: str = "extend",
        selectParentTemplates: Any = None,
        selectItems: str = None,
        monitored_hosts: int = 1,
    ) -> List[Dict[str, Any]]:
        """Retrieve all monitored hosts with full interface + group data."""
        params: Dict[str, Any] = {
            "output": output or [
                "hostid", "host", "name", "status",
                # Top-level availability fields (Zabbix < 6.4 style, kept for compat)
                "available",          # Zabbix Agent (type 1)
                "snmp_available",     # SNMP (type 2)
                "ipmi_available",     # IPMI (type 3)
                "jmx_available",      # JMX (type 4)
                # Maintenance fields
                "maintenance_status", # 0=no maintenance, 1=in maintenance
                "maintenance_from",   # Unix timestamp when maintenance started
                "maintenance_type",   # 0=with data collection, 1=without
                "error", "description",
            ],
            # Always request interfaces so we can detect Zabbix Agent / SNMP / HTTP Agent
            "selectInterfaces": selectInterfaces,
            # Always request groups for display
            "selectGroups": selectGroups,
            # Always request templates to map semantic agent types (protocol detection Step 3)
            "selectParentTemplates": selectParentTemplates or ["name"],
            # Only fetch monitored hosts (status=0 means monitored in Zabbix)
            "filter": {"status": "0"},
        }

        if selectItems:
            params["selectItems"] = selectItems

        result = await self._call("host.get", params)
        if result is None:
            logger.warning("host_get_returned_none")
            return []
        return result if isinstance(result, list) else []

    async def hostgroup_get(self) -> List[Dict[str, Any]]:
        """Retrieve all host groups."""
        params = {
            "output": ["groupid", "name"],
            "real_hosts": True,
        }
        result = await self._call("hostgroup.get", params)
        return result if isinstance(result, list) else []

    async def item_get(
        self,
        host_ids: List[str],
        *,
        key_search: Optional[str] = None,
        limit: int = 10000,
    ) -> List[Dict[str, Any]]:
        """Retrieve items (metrics) for given hosts."""
        params: Dict[str, Any] = {
            "output": [
                "itemid", "hostid", "name", "key_", "lastvalue",
                "units", "value_type", "lastclock", "status",
                "type",   # item type: 0=zabbix_agent, 19=http_agent, etc.
            ],
            "hostids": host_ids,
            "filter": {"status": "0"},  # only enabled items
            "limit": limit,
        }
        if key_search:
            params["search"] = {"key_": key_search}

        result = await self._call("item.get", params)
        return result if isinstance(result, list) else []

    async def trigger_get(
        self,
        *,
        only_true: bool = False,
        min_severity: int = 0,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Retrieve triggers."""
        params: Dict[str, Any] = {
            "output": ["triggerid", "description", "priority", "status",
                       "value", "lastchange", "error", "hosts"],
            "selectHosts": ["hostid", "host", "name"],
            "min_severity": min_severity,
            "sortfield": "priority",
            "sortorder": "DESC",
            "limit": limit,
            "filter": {"status": "0"}  # Zabbix 7.0+ compatibility (replaces monitored/active)
        }
        if only_true:
            params["filter"]["value"] = "1"  # TRIGGER_VALUE_TRUE (problem state)

        result = await self._call("trigger.get", params)
        return result if isinstance(result, list) else []

    async def problem_get(
        self,
        *,
        min_severity: int = 0,
        limit: int = 2000,
    ) -> List[Dict[str, Any]]:
        """Retrieve active problems."""
        params = {
            "output": ["eventid", "objectid", "clock", "name", "severity",
                       "acknowledged", "suppressed", "opdata"],
            "selectAcknowledges": ["message", "clock", "userid"],
            "selectTags": "extend",
            "recent": True,
            "severities": list(range(min_severity, 6)),
            "sortfield": ["severity", "clock"],
            "sortorder": "DESC",
            "limit": limit,
        }
        result = await self._call("problem.get", params)
        return result if isinstance(result, list) else []

    async def event_get(
        self,
        *,
        time_from: Optional[int] = None,
        time_till: Optional[int] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """Retrieve events within a time range."""
        params: Dict[str, Any] = {
            "output": ["eventid", "source", "object", "objectid",
                       "clock", "value", "acknowledged", "name", "severity"],
            "sortfield": "clock",
            "sortorder": "DESC",
            "limit": limit,
        }
        if time_from:
            params["time_from"] = time_from
        if time_till:
            params["time_till"] = time_till

        result = await self._call("event.get", params)
        return result if isinstance(result, list) else []

    async def history_get(
        self,
        item_ids: List[str],
        *,
        history_type: int = 0,
        time_from: Optional[int] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Retrieve historical data for given items."""
        params: Dict[str, Any] = {
            "output": "extend",
            "history": history_type,
            "itemids": item_ids,
            "sortfield": "clock",
            "sortorder": "DESC",
            "limit": limit,
        }
        if time_from:
            params["time_from"] = time_from

        result = await self._call("history.get", params)
        return result if isinstance(result, list) else []

    async def ping(self) -> bool:
        """Quick connectivity check — calls apiinfo.version."""
        payload = {
            "jsonrpc": "2.0",
            "method": "apiinfo.version",
            "params": [],
            "id": 0,
        }
        try:
            session = await self._get_session()
            async with session.post(self.api_url, json=payload) as resp:
                body = await resp.json(content_type=None)
                version = body.get("result", "")
                logger.info("zabbix_ping_ok", version=version)
                return bool(version)
        except Exception as exc:
            logger.warning("zabbix_ping_failed", error=str(exc))
            return False
