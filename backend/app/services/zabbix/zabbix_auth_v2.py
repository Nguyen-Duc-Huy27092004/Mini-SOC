"""
Zabbix Authentication Manager v2 - Supports both API tokens and user.login.

Zabbix 7.0+ introduced API tokens as the recommended authentication method.
This version supports:
  - Static API tokens (Zabbix 7.0+, recommended)
  - user.login with username/password (all versions, fallback)

Features:
- Async token cache with expiry buffer
- Thread-safe asyncio.Lock for concurrent requests
- Structured logging with structlog
- Graceful fallback from API token to user.login
- Backward compatible with Zabbix 5.x, 6.x, 7.x
"""
from __future__ import annotations

import asyncio
import time
from typing import Optional

import aiohttp
import structlog

logger = structlog.get_logger()

# Token lifetime buffer: refresh 5 minutes before expiry
_TOKEN_LIFETIME_SECONDS = 1500   # 25 minutes (Zabbix default session is 30m)
_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30, connect=10)


class ZabbixAuthManagerV2:
    """
    Manages Zabbix API authentication with support for both methods.

    Priority:
      1. If api_token is provided → use it directly (no authentication call)
      2. If user/password provided → use user.login (session token with refresh)

    Usage:
        # With API token (Zabbix 7.0+)
        auth = ZabbixAuthManagerV2(url, api_token="your_token")
        token = await auth.get_token(session)

        # With username/password (all versions)
        auth = ZabbixAuthManagerV2(url, user="admin", password="pass")
        token = await auth.get_token(session)
    """

    def __init__(
        self,
        api_url: str,
        user: Optional[str] = None,
        password: Optional[str] = None,
        api_token: Optional[str] = None,
    ) -> None:
        self.api_url = api_url
        self._user = user
        self._password = password
        self._api_token = api_token
        self._session_token: Optional[str] = None
        self._token_acquired_at: float = 0.0
        self._lock = asyncio.Lock()

        # Validate configuration
        if not api_token and not (user and password):
            raise ValueError(
                "Either api_token or both user+password must be provided"
            )

        # Log authentication method
        if api_token:
            logger.info(
                "zabbix_auth_mode",
                mode="api_token",
                url=api_url,
                token_preview=api_token[:8] + "..." if len(api_token) > 8 else "***",
            )
        else:
            logger.info(
                "zabbix_auth_mode",
                mode="user_login",
                url=api_url,
                user=user,
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_token(self, session: aiohttp.ClientSession) -> Optional[str]:
        """Return a valid authentication token."""
        async with self._lock:
            # Priority 1: Static API token (Zabbix 7.0+)
            if self._api_token:
                logger.debug("zabbix_auth_using_static_token")
                return self._api_token

            # Priority 2: Session token via user.login (all versions)
            if self._is_session_token_valid():
                logger.debug("zabbix_auth_using_cached_session")
                return self._session_token

            logger.debug("zabbix_auth_refreshing_session")
            return await self._authenticate(session)

    async def invalidate(self) -> None:
        """Force token refresh on next call (e.g. after 401)."""
        async with self._lock:
            # Only invalidate session tokens, not static API tokens
            if not self._api_token:
                self._session_token = None
                self._token_acquired_at = 0.0
                logger.info("zabbix_session_token_invalidated")
            else:
                logger.warning(
                    "zabbix_api_token_invalid",
                    message="Static API token may be invalid or expired. "
                            "Check Zabbix UI: Administration → General → API tokens"
                )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_session_token_valid(self) -> bool:
        """Check if cached session token is still valid."""
        if not self._session_token:
            return False
        age = time.monotonic() - self._token_acquired_at
        return age < _TOKEN_LIFETIME_SECONDS

    async def _authenticate(self, session: aiohttp.ClientSession) -> Optional[str]:
        """Perform user.login JSON-RPC call to get session token."""
        if not self._user or not self._password:
            logger.error("zabbix_auth_no_credentials")
            return None

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
                    self._session_token = None
                    return None

                token = body.get("result")
                if not token or not isinstance(token, str):
                    logger.error(
                        "zabbix_auth_no_token",
                        result=str(body.get("result", ""))[:100]
                    )
                    return None

                self._session_token = token
                self._token_acquired_at = time.monotonic()
                logger.info(
                    "zabbix_authenticated",
                    token_preview=token[:8] + "...",
                    expires_in=f"{_TOKEN_LIFETIME_SECONDS}s"
                )
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

    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------

    @property
    def is_using_api_token(self) -> bool:
        """Check if using static API token vs session token."""
        return self._api_token is not None

    @property
    def auth_method(self) -> str:
        """Get current authentication method name."""
        return "api_token" if self._api_token else "user_login"

