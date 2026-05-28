"""
Secure HttpOnly Cookie Helpers

Production-grade authentication cookie management:
- HttpOnly JWT cookies
- CSRF token cookie
- Secure cookie policy
- Proper deletion handling
- Multi-environment support
"""

from __future__ import annotations

from typing import Final

import structlog
from fastapi import Response

from app.core.config import settings

logger = structlog.get_logger()

ACCESS_COOKIE: Final[str] = "soc_access_token"
REFRESH_COOKIE: Final[str] = "soc_refresh_token"
CSRF_COOKIE: Final[str] = "soc_csrf_token"


def _cookie_secure() -> bool:
    """
    Whether cookies should require HTTPS.
    Explicit setting is safer than ENV guessing.
    """
    return settings.COOKIE_SECURE


def _cookie_domain() -> str | None:
    """
    Optional shared domain:
    Example: .company.local
    """
    domain = settings.COOKIE_DOMAIN.strip()
    return domain or None


def _base_cookie_config() -> dict:
    """
    Shared cookie configuration.
    """
    return {
        "secure": _cookie_secure(),
        "domain": _cookie_domain(),
    }


def set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    csrf_token: str,
) -> None:
    """
    Set authentication cookies securely.
    """

    base = _base_cookie_config()

    # ---------------------------------------------------------
    # Access Token
    # ---------------------------------------------------------
    response.set_cookie(
        key=ACCESS_COOKIE,
        value=access_token,
        httponly=True,
        secure=base["secure"],
        samesite="strict",
        domain=base["domain"],
        path="/",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    # ---------------------------------------------------------
    # Refresh Token
    # ---------------------------------------------------------
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=refresh_token,
        httponly=True,
        secure=base["secure"],
        samesite="strict",
        domain=base["domain"],
        path="/api/v1/auth",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )

    # ---------------------------------------------------------
    # CSRF Token
    # JS-readable intentionally
    # ---------------------------------------------------------
    response.set_cookie(
        key=CSRF_COOKIE,
        value=csrf_token,
        httponly=False,
        secure=base["secure"],
        samesite="strict",
        domain=base["domain"],
        path="/",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )

    logger.debug("auth_cookies_set")


def clear_auth_cookies(response: Response) -> None:
    """
    Clear all auth-related cookies.
    """

    base = _base_cookie_config()

    cookie_configs = [
        (ACCESS_COOKIE, "/"),
        (REFRESH_COOKIE, "/api/v1/auth"),
        (CSRF_COOKIE, "/"),
    ]

    for cookie_name, cookie_path in cookie_configs:
        response.delete_cookie(
            key=cookie_name,
            path=cookie_path,
            domain=base["domain"],
            secure=base["secure"],
            samesite="strict",
        )

    logger.debug("auth_cookies_cleared")