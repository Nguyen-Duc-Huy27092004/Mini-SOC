"""
Zabbix 7.4 API Client with API Token Authentication

Professional implementation for Mini-SOC Infrastructure Monitoring.
Uses Zabbix 7.4 JSON-RPC API with API Token authentication.

Author: Principal Zabbix Engineer & SOC Architect
Date: 2026-06-17
Version: 7.4.0
"""
from __future__ import annotations

import asyncio
import ssl
import time
from typing import Any, Dict, List, Optional

import aiohttp
import structlog

logger = structlog.get_logger(__name__)

# Configuration constants
_MAX_RETRIES = 3
_BACKOFF_BASE = 1.5
_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30, connect=10, sock_read=25)
_RPC_ID_COUNTER = 0


def _next_rpc_id() -> int:
    """Generate unique RPC request ID."""
    global _RPC_ID_COUNTER
    _RPC_ID_COUNTER = (_RPC_ID_COUNTER + 1) % 100_000
    return _RPC_ID_COUNTER


class ZabbixClientV7:
    """
    Professional Zabbix 7.4 API Client for Mini-SOC.
    
    Features:
    - API Token authentication (Zabbix 7.0+)
    - Async aiohttp with connection pooling
    - Automatic retry with exponential backoff
    - Comprehensive error handling
    - Structured logging
    - Request/response timing metrics
    
    All methods return clean, normalized data or empty structures on error.
    Never raises exceptions to upstream callers.
    """

    def __init__(
        self,
        api_url: str,
        api_token: str,
        verify_ssl: bool = True,
        timeout: int = 30,
    ) -> None:
        """
        Initialize Zabbix 7.4 API client.
        
        Args:
            api_url: Zabbix API endpoint URL
            api_token: API token from Zabbix UI (Administration → General → API tokens)
            verify_ssl: Whether to verify SSL certificates
            timeout: Request timeout in seconds
        """
        self.api_url = api_url
        self._api_token = api_token
        self._verify_ssl = verify_ssl
        self._timeout = aiohttp.ClientTimeout(total=timeout, connect=10)
        self._session: Optional[aiohttp.ClientSession] = None
        
        logger.info(
            "zabbix_client_initialized",
            url=api_url,
            token_preview=api_token[:8] + "..." if len(api_token) > 8 else "***",
            verify_ssl=verify_ssl,
        )

    # ================================================================
    # Session Management
    # ================================================================

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session with proper SSL context."""
        if self._session and not self._session.closed:
            return self._session

        # Configure SSL
        if self._verify_ssl:
            ssl_ctx: bool | ssl.SSLContext = True
        else:
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE

        # Create session with connection pooling
        connector = aiohttp.TCPConnector(
            ssl=ssl_ctx,
            limit=20,  # Max concurrent connections
            limit_per_host=10,
            ttl_dns_cache=300,
        )
        
        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=self._timeout,
            headers={
                "Content-Type": "application/json-rpc",
                "Authorization": f"Bearer {self._api_token}",
            },
            raise_for_status=False,
        )
        
        logger.debug("zabbix_session_created")
        return self._session

    async def close(self) -> None:
        """Close aiohttp session and cleanup resources."""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.info("zabbix_client_closed")

    # ================================================================
    # Core JSON-RPC Communication
    # ================================================================

    async def _call(
        self,
        method: str,
        params: Dict[str, Any],
        retry_count: int = 0,
    ) -> Optional[Any]:
        """
        Execute JSON-RPC call with retry and error handling.
        
        Args:
            method: Zabbix API method name
            params: Method parameters
            retry_count: Current retry attempt
            
        Returns:
            API response result or None on error
        """
        session = await self._get_session()

        # Build JSON-RPC request (without 'auth' in payload for Zabbix 7.4+)
        payload: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": _next_rpc_id(),
        }

        start_time = time.monotonic()
        logger.debug(
            "zabbix_request_start",
            method=method,
            url=self.api_url,
            retry=retry_count,
        )

        try:
            async with session.post(self.api_url, json=payload) as resp:
                latency_ms = round((time.monotonic() - start_time) * 1000, 2)
                status_code = resp.status
                
                # Read response
                try:
                    body = await resp.json(content_type=None)
                except Exception:
                    body_text = await resp.text()
                    logger.error(
                        "zabbix_response_parse_error",
                        method=method,
                        status=status_code,
                        body_preview=body_text[:300],
                    )
                    return None

                logger.debug(
                    "zabbix_response_received",
                    method=method,
                    status=status_code,
                    latency_ms=latency_ms,
                    has_result="result" in body,
                    has_error="error" in body,
                )

                # Handle successful response
                if status_code == 200:
                    # Check for API-level errors
                    if "error" in body:
                        error = body["error"]
                        error_code = error.get("code")
                        error_message = error.get("message", "")
                        error_data = error.get("data", "")
                        
                        logger.error(
                            "zabbix_api_error",
                            method=method,
                            code=error_code,
                            message=error_message,
                            data=str(error_data)[:200],
                        )
                        
                        # API token invalid or expired
                        if "Session terminated" in str(error_data) or error_code == -32602:
                            logger.error(
                                "zabbix_token_invalid",
                                message="API token is invalid or expired. "
                                        "Check Zabbix UI: Administration → General → API tokens"
                            )
                        
                        return None

                    # Success - return result
                    result = body.get("result")
                    logger.info(
                        "zabbix_request_success",
                        method=method,
                        latency_ms=latency_ms,
                        result_type=type(result).__name__,
                        result_count=len(result) if isinstance(result, (list, dict)) else None,
                    )
                    return result

                # Handle HTTP-level errors with retry
                if status_code in (429, 500, 502, 503, 504) and retry_count < _MAX_RETRIES:
                    backoff = _BACKOFF_BASE ** retry_count
                    logger.warning(
                        "zabbix_request_retrying",
                        method=method,
                        status=status_code,
                        retry=retry_count + 1,
                        backoff_seconds=backoff,
                    )
                    await asyncio.sleep(backoff)
                    return await self._call(method, params, retry_count + 1)

                logger.error(
                    "zabbix_request_failed",
                    method=method,
                    status=status_code,
                    latency_ms=latency_ms,
                )
                return None

        except asyncio.TimeoutError:
            logger.warning(
                "zabbix_request_timeout",
                method=method,
                timeout_seconds=self._timeout.total,
            )
            if retry_count < _MAX_RETRIES:
                await asyncio.sleep(_BACKOFF_BASE ** retry_count)
                return await self._call(method, params, retry_count + 1)
            return None

        except aiohttp.ClientError as exc:
            logger.error(
                "zabbix_client_error",
                method=method,
                error_type=type(exc).__name__,
                error=str(exc),
            )
            return None

        except Exception as exc:
            logger.exception(
                "zabbix_request_exception",
                method=method,
                error_type=type(exc).__name__,
                error=str(exc),
            )
            return None

    # ================================================================
    # Zabbix 7.4 API Methods - Infrastructure Overview
    # ================================================================

    async def host_get(
        self,
        *,
        output: Optional[List[str]] = None,
        selectGroups: Optional[str] = None,
        selectInterfaces: Optional[str] = None,
        selectItems: Optional[str] = None,
        selectTriggers: Optional[str] = None,
        monitored_hosts: Optional[int] = None,
        search: Optional[Dict[str, Any]] = None,
        filter: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve hosts from Zabbix.
        
        Returns list of hosts with full details for infrastructure overview.
        """
        params: Dict[str, Any] = {
            "output": output or [
                "hostid", "host", "name", "status", "available",
                "description", "maintenance_status", "ipmi_available",
                "error", "items_num", "maintenance_from", "maintenance_type",
            ],
        }
        
        if selectGroups is not None:
            params["selectGroups"] = selectGroups
        if selectInterfaces is not None:
            params["selectInterfaces"] = selectInterfaces
        if selectItems is not None:
            params["selectItems"] = selectItems
        if selectTriggers is not None:
            params["selectTriggers"] = selectTriggers
        if monitored_hosts is not None:
            params["monitored_hosts"] = monitored_hosts
        if search:
            params["search"] = search
        if filter:
            params["filter"] = filter
        if limit:
            params["limit"] = limit

        result = await self._call("host.get", params)
        return result if isinstance(result, list) else []

    async def hostgroup_get(
        self,
        *,
        output: Optional[List[str]] = None,
        real_hosts: bool = True,
    ) -> List[Dict[str, Any]]:
        """Retrieve host groups."""
        params: Dict[str, Any] = {
            "output": output or ["groupid", "name"],
            "real_hosts": real_hosts,
        }
        result = await self._call("hostgroup.get", params)
        return result if isinstance(result, list) else []

    # ================================================================
    # Problem Monitoring
    # ================================================================

    async def problem_get(
        self,
        *,
        output: Optional[List[str]] = None,
        selectAcknowledges: Optional[str] = None,
        selectTags: Optional[str] = None,
        selectSuppressionData: Optional[str] = None,
        recent: bool = True,
        severities: Optional[List[int]] = None,
        acknowledged: Optional[bool] = None,
        suppressed: Optional[bool] = None,
        time_from: Optional[int] = None,
        time_till: Optional[int] = None,
        sortfield: Optional[List[str]] = None,
        sortorder: str = "DESC",
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve active problems.
        
        Essential for Problem Monitoring dashboard.
        """
        params: Dict[str, Any] = {
            "output": output or [
                "eventid", "objectid", "clock", "ns", "name",
                "severity", "r_eventid", "acknowledged",
                "suppressed", "opdata", "urls",
            ],
            "recent": recent,
            "sortorder": sortorder,
        }
        
        if selectAcknowledges is not None:
            params["selectAcknowledges"] = selectAcknowledges
        if selectTags is not None:
            params["selectTags"] = selectTags
        if selectSuppressionData is not None:
            params["selectSuppressionData"] = selectSuppressionData
        if severities is not None:
            params["severities"] = severities
        if acknowledged is not None:
            params["acknowledged"] = acknowledged
        if suppressed is not None:
            params["suppressed"] = suppressed
        if time_from:
            params["time_from"] = time_from
        if time_till:
            params["time_till"] = time_till
        if sortfield:
            params["sortfield"] = sortfield
        if limit:
            params["limit"] = limit

        result = await self._call("problem.get", params)
        return result if isinstance(result, list) else []

    async def trigger_get(
        self,
        *,
        output: Optional[List[str]] = None,
        selectHosts: Optional[str] = None,
        selectGroups: Optional[str] = None,
        selectFunctions: Optional[str] = None,
        selectTags: Optional[str] = None,
        monitored: bool = True,
        active: bool = True,
        only_true: Optional[bool] = None,
        min_severity: Optional[int] = None,
        maintenance: Optional[bool] = None,
        sortfield: Optional[List[str]] = None,
        sortorder: str = "DESC",
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve triggers with full context."""
        params: Dict[str, Any] = {
            "output": output or [
                "triggerid", "description", "expression", "priority",
                "status", "value", "lastchange", "error", "recovery_mode",
                "manual_close", "opdata", "url",
            ],
            "monitored": monitored,
            "active": active,
            "sortorder": sortorder,
        }
        
        if selectHosts is not None:
            params["selectHosts"] = selectHosts
        if selectGroups is not None:
            params["selectGroups"] = selectGroups
        if selectFunctions is not None:
            params["selectFunctions"] = selectFunctions
        if selectTags is not None:
            params["selectTags"] = selectTags
        if only_true is not None:
            params["value"] = 1 if only_true else 0
        if min_severity is not None:
            params["min_severity"] = min_severity
        if maintenance is not None:
            params["maintenance"] = maintenance
        if sortfield:
            params["sortfield"] = sortfield
        if limit:
            params["limit"] = limit

        result = await self._call("trigger.get", params)
        return result if isinstance(result, list) else []

    async def event_get(
        self,
        *,
        output: Optional[List[str]] = None,
        selectHosts: Optional[str] = None,
        selectRelatedObject: Optional[str] = None,
        selectTags: Optional[str] = None,
        selectSuppressionData: Optional[str] = None,
        source: Optional[int] = None,
        object: Optional[int] = None,
        time_from: Optional[int] = None,
        time_till: Optional[int] = None,
        value: Optional[List[int]] = None,
        sortfield: Optional[List[str]] = None,
        sortorder: str = "DESC",
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve events for timeline visualization."""
        params: Dict[str, Any] = {
            "output": output or [
                "eventid", "source", "object", "objectid",
                "clock", "ns", "value", "acknowledged",
                "name", "severity", "r_eventid", "suppressed",
            ],
            "sortorder": sortorder,
        }
        
        if selectHosts is not None:
            params["selectHosts"] = selectHosts
        if selectRelatedObject is not None:
            params["selectRelatedObject"] = selectRelatedObject
        if selectTags is not None:
            params["selectTags"] = selectTags
        if selectSuppressionData is not None:
            params["selectSuppressionData"] = selectSuppressionData
        if source is not None:
            params["source"] = source
        if object is not None:
            params["object"] = object
        if time_from:
            params["time_from"] = time_from
        if time_till:
            params["time_till"] = time_till
        if value is not None:
            params["value"] = value
        if sortfield:
            params["sortfield"] = sortfield
        if limit:
            params["limit"] = limit

        result = await self._call("event.get", params)
        return result if isinstance(result, list) else []

    # ================================================================
    # Resource Monitoring
    # ================================================================

    async def item_get(
        self,
        *,
        output: Optional[List[str]] = None,
        hostids: Optional[List[str]] = None,
        groupids: Optional[List[str]] = None,
        search: Optional[Dict[str, Any]] = None,
        filter: Optional[Dict[str, Any]] = None,
        monitored: bool = True,
        selectHosts: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve items (metrics) for resource monitoring.
        
        Used for CPU, memory, disk, network utilization tracking.
        """
        params: Dict[str, Any] = {
            "output": output or [
                "itemid", "hostid", "name", "key_", "type",
                "value_type", "units", "lastvalue", "lastclock",
                "prevvalue", "status", "state", "error",
            ],
            "monitored": monitored,
        }
        
        if hostids:
            params["hostids"] = hostids
        if groupids:
            params["groupids"] = groupids
        if search:
            params["search"] = search
        if filter:
            params["filter"] = filter
        if selectHosts is not None:
            params["selectHosts"] = selectHosts
        if limit:
            params["limit"] = limit

        result = await self._call("item.get", params)
        return result if isinstance(result, list) else []

    async def history_get(
        self,
        *,
        output: str = "extend",
        history: int,
        itemids: List[str],
        time_from: Optional[int] = None,
        time_till: Optional[int] = None,
        sortfield: Optional[List[str]] = None,
        sortorder: str = "DESC",
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve historical data for trending and analysis.
        
        Args:
            history: Value type (0=float, 1=str, 2=log, 3=int, 4=text)
        """
        params: Dict[str, Any] = {
            "output": output,
            "history": history,
            "itemids": itemids,
            "sortorder": sortorder,
        }
        
        if time_from:
            params["time_from"] = time_from
        if time_till:
            params["time_till"] = time_till
        if sortfield:
            params["sortfield"] = sortfield
        if limit:
            params["limit"] = limit

        result = await self._call("history.get", params)
        return result if isinstance(result, list) else []

    # ================================================================
    # Maintenance Management
    # ================================================================

    async def maintenance_get(
        self,
        *,
        output: Optional[List[str]] = None,
        selectGroups: Optional[str] = None,
        selectHosts: Optional[str] = None,
        selectTimeperiods: Optional[str] = None,
        sortfield: Optional[List[str]] = None,
        sortorder: str = "ASC",
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve maintenance schedules."""
        params: Dict[str, Any] = {
            "output": output or [
                "maintenanceid", "name", "maintenance_type",
                "description", "active_since", "active_till",
                "tags_evaltype",
            ],
            "sortorder": sortorder,
        }
        
        if selectGroups is not None:
            params["selectGroups"] = selectGroups
        if selectHosts is not None:
            params["selectHosts"] = selectHosts
        if selectTimeperiods is not None:
            params["selectTimeperiods"] = selectTimeperiods
        if sortfield:
            params["sortfield"] = sortfield
        if limit:
            params["limit"] = limit

        result = await self._call("maintenance.get", params)
        return result if isinstance(result, list) else []

    # ================================================================
    # Utility Methods
    # ================================================================

    async def apiinfo_version(self) -> Optional[str]:
        """
        Get Zabbix API version.
        
        Useful for connectivity check and version verification.
        """
        payload = {
            "jsonrpc": "2.0",
            "method": "apiinfo.version",
            "params": [],
            "id": _next_rpc_id(),
        }
        
        try:
            session = await self._get_session()
            async with session.post(self.api_url, json=payload) as resp:
                body = await resp.json(content_type=None)
                version = body.get("result", "")
                logger.info("zabbix_version_check", version=version)
                return version
        except Exception as exc:
            logger.warning("zabbix_version_check_failed", error=str(exc))
            return None

    async def ping(self) -> bool:
        """Quick connectivity and authentication check."""
        version = await self.apiinfo_version()
        return version is not None and version.startswith(("7.", "6.", "5."))

