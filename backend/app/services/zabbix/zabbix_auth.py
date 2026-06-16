"""
Zabbix Authentication Manager.

Handles JSON-RPC token acquisition, caching, and refresh
for Zabbix API v5.x / v6.x / v7.x.

Features:
- Async token cache with expiry buffer (token valid for 30min, refresh at 25min)
- Thread-safe asyncio.Lock for concurrent requests
- Structured logging with structlog
- Graceful failure — returns None on auth error (caller handles fallback)
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Optional

import aiohttp
import structlog

logger = structlog.get_logger()

# Token lifetime buffer: refresh 5 minutes before expiry
_TOKEN_LIFETIME_SECONDS = 1500   # 25 minutes (Zabbix default is 30m)
_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30, connect=10)


class ZabbixAuthManager:
    """
    Manages Zabbix API token lifecycle.

    Usage:
        auth = ZabbixAuthManager(url, user, password)
        token = await auth.get_token(session)
    """

    def __init__(self, api_url: str, user: str, password: str) -> None:
        self.api_url = api_url
        self._user = user
        self._password = password
        self._token: Optional[str] = None
        self._token_acquired_at: float = 0.0
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_token(self, session: aiohttp.ClientSession) -> Optional[str]:
        """Return a valid token, refreshing if necessary."""
        async with self._lock:
            if self._is_token_valid():
                return self._token
            return await self._authenticate(session)

    async def invalidate(self) -> None:
        """Force token refresh on next call (e.g. after 401)."""
        async with self._lock:
            self._token = None
            self._token_acquired_at = 0.0
            logger.info("zabbix_token_invalidated")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_token_valid(self) -> bool:
        if not self._token:
            return False
        age = time.monotonic() - self._token_acquired_at
        return age < _TOKEN_LIFETIME_SECONDS

    async def _authenticate(self, session: aiohttp.ClientSession) -> Optional[str]:
        """Perform user.login JSON-RPC call."""
        payload = {
            "jsonrpc": "2.0",
            "method": "user.login",
            "params": {
                "user": self._user,
                "password": self._password,
            },
            "id": 1,
        }

        logger.info(
            "zabbix_authenticating",
            url=self.api_url,
            user=self._user,
        )

        try:
            async with session.post(
                self.api_url,
                json=payload,
                timeout=_REQUEST_TIMEOUT,
            ) as resp:
                status = resp.status
                body = await resp.json(content_type=None)

                logger.debug(
                    "zabbix_auth_response",
                    status=status,
                    has_result="result" in body,
                    has_error="error" in body,
                )

                if "error" in body:
                    err = body["error"]
                    logger.error(
                        "zabbix_auth_failed",
                        code=err.get("code"),
                        data=err.get("data"),
                        message=err.get("message"),
                    )
                    self._token = None
                    return None

                token = body.get("result")
                if not token or not isinstance(token, str):
                    logger.error("zabbix_auth_no_token", result=str(body.get("result", ""))[:100])
                    return None

                self._token = token
                self._token_acquired_at = time.monotonic()
                logger.info("zabbix_authenticated", token_preview=token[:8] + "...")
                return token

        except asyncio.TimeoutError:
            logger.error("zabbix_auth_timeout", url=self.api_url)
            return None
        except aiohttp.ClientError as exc:
            logger.error("zabbix_auth_client_error", error=str(exc))
            return None
        except Exception as exc:
            logger.exception("zabbix_auth_exception", error=str(exc))
            return None
