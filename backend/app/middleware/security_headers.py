"""
Security Headers Middleware
Production-grade security headers for OWASP compliance.
"""

from __future__ import annotations

from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add security headers to all responses.
    
    Implements OWASP recommendations:
    - X-Content-Type-Options
    - X-Frame-Options
    - X-XSS-Protection
    - Strict-Transport-Security (HSTS)
    - Content-Security-Policy (CSP)
    - Referrer-Policy
    - Permissions-Policy
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:

        response = await call_next(request)

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # XSS Protection (legacy, but still useful)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Force HTTPS (only in production)
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # Content Security Policy
        # Adjust based on your frontend needs
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'",  # React needs eval
            "style-src 'self' 'unsafe-inline'",  # Tailwind needs inline
            "img-src 'self' data: https:",
            "font-src 'self' data:",
            "connect-src 'self' ws: wss:",  # WebSocket
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
        ]

        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

        # Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions Policy (formerly Feature-Policy)
        permissions = [
            "geolocation=()",
            "microphone=()",
            "camera=()",
            "payment=()",
            "usb=()",
        ]

        response.headers["Permissions-Policy"] = ", ".join(permissions)

        # Remove server header (security through obscurity)
        # MutableHeaders doesn't have pop(), use del with try-except
        try:
            del response.headers["Server"]
        except KeyError:
            pass

        return response
