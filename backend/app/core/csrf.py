"""
CSRF Protection Utilities

Implements hardened double-submit CSRF protection:
- Secure token generation
- Timing-safe validation
- Origin validation
- Structured security logging
"""

from __future__ import annotations

import secrets
from typing import Final

import structlog
from fastapi import HTTPException, Request, status

from app.core.config import settings
from app.core.cookies import CSRF_COOKIE

logger = structlog.get_logger()

CSRF_HEADER_NAME: Final[str] = "X-CSRF-Token"

SAFE_METHODS = {
    "GET",
    "HEAD",
    "OPTIONS",
}


def generate_csrf_token() -> str:
    """
    Generate cryptographically secure CSRF token.
    """
    return secrets.token_urlsafe(32)


def validate_csrf(request: Request) -> None:
    """
    Validate CSRF token using hardened double-submit strategy.
    """

    if request.method.upper() in SAFE_METHODS:
        return

    header_token = request.headers.get(CSRF_HEADER_NAME)
    cookie_token = request.cookies.get(CSRF_COOKIE)

    if not header_token or not cookie_token:
        logger.warning(
            "csrf_missing_token",
            client=request.client.host if request.client else None,
            path=request.url.path,
            method=request.method,
        )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF token",
        )

    # Timing-safe comparison
    if not secrets.compare_digest(header_token, cookie_token):
        logger.warning(
            "csrf_token_mismatch",
            client=request.client.host if request.client else None,
            path=request.url.path,
            method=request.method,
        )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF token",
        )

    # ---------------------------------------------------------
    # Optional Origin Validation
    # ---------------------------------------------------------
    if settings.CSRF_VALIDATE_ORIGIN:
        origin = request.headers.get("Origin")

        if origin:
            allowed_origins = settings.BACKEND_CORS_ORIGINS

            if origin not in allowed_origins:
                logger.warning(
                    "csrf_origin_validation_failed",
                    origin=origin,
                    path=request.url.path,
                )

                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Origin validation failed",
                )