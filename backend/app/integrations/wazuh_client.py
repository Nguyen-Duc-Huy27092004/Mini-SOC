"""
Production-grade Wazuh API Client

Features:
- Async aiohttp client
- Connection pooling
- Token caching with expiry buffer
- Safe retry with exponential backoff
- Structured logging
- Health tracking
- Timeout protection
- Batch rule fetching
- Production-safe error handling
"""

from __future__ import annotations

import asyncio
import ssl
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import aiohttp
import structlog

logger = structlog.get_logger()


class WazuhAPIClient:
    """Production-ready async Wazuh API client."""

    MAX_RETRIES = 3
    RETRY_BACKOFF = 1.5

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        verify_ssl: bool = True,
        timeout: int = 30,
        max_connections: int = 20,
    ) -> None:

        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password

        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.max_connections = max_connections

        self._session: Optional[aiohttp.ClientSession] = None

        self._token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

        self._is_healthy = True
        self._last_error: Optional[str] = None

        self._auth_lock = asyncio.Lock()

    # ============================================================
    # Session Management
    # ============================================================

    async def _get_session(self) -> aiohttp.ClientSession:

        if self._session and not self._session.closed:
            return self._session

        # Build ssl context properly so self-signed certs are accepted
        if self.verify_ssl:
            ssl_context: bool | ssl.SSLContext = True
        else:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

        connector = aiohttp.TCPConnector(
            ssl=ssl_context,
            limit=self.max_connections,
            ttl_dns_cache=300,
        )

        timeout = aiohttp.ClientTimeout(
            total=self.timeout,
            connect=10,
            sock_read=self.timeout,
        )

        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            raise_for_status=False,
        )

        return self._session

    # ============================================================
    # Authentication
    # ============================================================

    async def _authenticate(self) -> Optional[str]:

        async with self._auth_lock:

            if (
                self._token
                and self._token_expires_at
                and datetime.now(timezone.utc) < self._token_expires_at
            ):
                return self._token

            try:

                session = await self._get_session()

                url = urljoin(
                    self.base_url + "/",
                    "security/user/authenticate",
                )

                logger.info(
                    "wazuh_authenticating",
                    url=url,
                    user=self.username,
                    verify_ssl=self.verify_ssl,
                )

                start = time.monotonic()

                async with session.post(
                    url,
                    auth=aiohttp.BasicAuth(
                        self.username,
                        self.password,
                    ),
                ) as response:

                    latency = round(time.monotonic() - start, 3)

                    if response.status != 200:

                        body = await response.text()

                        logger.error(
                            "wazuh_auth_failed",
                            status=response.status,
                            latency=latency,
                            body_preview=body[:300],
                        )

                        self._is_healthy = False
                        return None

                    data = await response.json()

                    token = data.get("data", {}).get("token")

                    if not token:

                        logger.error(
                            "wazuh_auth_no_token"
                        )

                        return None

                    self._token = token

                    self._token_expires_at = (
                        datetime.now(timezone.utc)
                        + timedelta(minutes=10)
                    )

                    self._is_healthy = True

                    logger.info(
                        "wazuh_authenticated",
                        latency=latency,
                    )

                    return token

            except Exception as exc:

                self._last_error = str(exc)

                logger.exception(
                    "wazuh_auth_exception",
                )

                return None

    # ============================================================
    # HTTP Request
    # ============================================================

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        retry_count: int = 0,
    ) -> Optional[Dict[str, Any]]:

        token = await self._authenticate()

        if not token:
            return None

        try:

            session = await self._get_session()

            url = urljoin(self.base_url, endpoint)

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            start = time.monotonic()

            async with session.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                headers=headers,
            ) as response:

                latency = round(time.monotonic() - start, 3)

                if response.status == 401:

                    logger.warning(
                        "wazuh_token_expired",
                        endpoint=endpoint,
                    )

                    self._token = None

                    if retry_count >= self.MAX_RETRIES:
                        return None

                    return await self._request(
                        method,
                        endpoint,
                        params,
                        json_data,
                        retry_count + 1,
                    )

                if response.status in (429, 500, 502, 503, 504):

                    if retry_count < self.MAX_RETRIES:

                        backoff = (
                            self.RETRY_BACKOFF ** retry_count
                        )

                        logger.warning(
                            "wazuh_retrying_request",
                            endpoint=endpoint,
                            status=response.status,
                            retry=retry_count + 1,
                            backoff=backoff,
                        )

                        await asyncio.sleep(backoff)

                        return await self._request(
                            method,
                            endpoint,
                            params,
                            json_data,
                            retry_count + 1,
                        )

                if response.status >= 400:

                    body = await response.text()

                    logger.warning(
                        "wazuh_request_failed",
                        endpoint=endpoint,
                        status=response.status,
                        latency=latency,
                        body_preview=body[:300],
                    )

                    return None

                try:

                    data = await response.json()

                    logger.debug(
                        "wazuh_request_success",
                        endpoint=endpoint,
                        latency=latency,
                    )

                    return data

                except Exception:

                    body = await response.text()

                    logger.warning(
                        "wazuh_invalid_json_response",
                        endpoint=endpoint,
                        body_preview=body[:300],
                    )

                    return None

        except asyncio.TimeoutError:

            logger.warning(
                "wazuh_request_timeout",
                endpoint=endpoint,
            )

            return None

        except aiohttp.ClientError:

            logger.exception(
                "wazuh_client_error",
                endpoint=endpoint,
            )

            return None

        except Exception:

            logger.exception(
                "wazuh_request_exception",
                endpoint=endpoint,
            )

            return None

    # ============================================================
    # API Methods
    # ============================================================

    async def get_agents(
        self,
        limit: int = 500,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:

        response = await self._request(
            "GET",
            "/agents",
            params={
                "limit": limit,
                "offset": offset,
            },
        )

        if not response:
            logger.error(
                "get_agents_failed",
                reason="no_response_from_wazuh_api",
                endpoint="/agents",
            )
            return []

        items = response.get("data", {}).get(
            "affected_items",
            [],
        )
        
        logger.info(
            "get_agents_success",
            count=len(items),
            limit=limit,
            offset=offset,
        )
        
        return items

    async def get_agent_detail(
        self,
        agent_id: str,
    ) -> Optional[Dict[str, Any]]:

        response = await self._request(
            "GET",
            f"/agents/{agent_id}",
        )

        if not response:
            return None

        items = response.get("data", {}).get(
            "affected_items",
            [],
        )

        return items[0] if items else None

    async def get_alerts(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:

        response = await self._request(
            "GET",
            "/alerts",
            params={
                "limit": limit,
                "offset": offset,
            },
        )

        if not response:
            return []

        return response.get("data", {}).get(
            "affected_items",
            [],
        )

    async def get_rules(
        self,
        rule_ids: List[str],
    ) -> Dict[str, Dict[str, Any]]:

        rules: Dict[str, Dict[str, Any]] = {}

        async def fetch(rule_id: str):

            response = await self._request(
                "GET",
                "/rules",
                params={"rule_ids": rule_id},
            )

            if not response:
                return

            items = response.get("data", {}).get(
                "affected_items",
                [],
            )

            if items:
                rules[rule_id] = items[0]

        await asyncio.gather(
            *[
                fetch(rule_id)
                for rule_id in rule_ids[:100]
            ]
        )

        return rules

    async def get_manager_info(
        self,
    ) -> Optional[Dict[str, Any]]:

        response = await self._request(
            "GET",
            "/manager/info",
        )

        if not response:
            return None

        items = response.get("data", {}).get(
            "affected_items",
            [],
        )

        return items[0] if items else None

    # ============================================================
    # Health
    # ============================================================

    def health(self) -> Dict[str, Any]:

        return {
            "healthy": self._is_healthy,
            "last_error": self._last_error,
            "authenticated": bool(self._token),
        }

    # ============================================================
    # Shutdown
    # ============================================================

    async def close(self) -> None:

        if self._session:

            await self._session.close()

            self._session = None

            logger.info(
                "wazuh_client_closed"
            )