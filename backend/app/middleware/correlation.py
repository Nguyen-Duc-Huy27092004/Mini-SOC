"""
Production-grade Correlation ID Middleware

Features:
- ASGI-native middleware (faster than BaseHTTPMiddleware)
- Safe request ID handling
- Request tracing
- Structured logging context
- Latency tracking
- Exception-safe cleanup
"""

from __future__ import annotations

import time
import uuid
from typing import Callable

import structlog
from starlette.types import (
    ASGIApp,
    Message,
    Receive,
    Scope,
    Send,
)

logger = structlog.get_logger()

REQUEST_ID_HEADER = b"x-request-id"
MAX_REQUEST_ID_LENGTH = 128


class CorrelationIdMiddleware:
    """
    Production-ready request tracing middleware.
    """

    def __init__(
        self,
        app: ASGIApp,
    ) -> None:

        self.app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:

        if scope["type"] != "http":

            await self.app(scope, receive, send)
            return

        request_id = self._extract_request_id(scope)

        client = scope.get("client")
        client_ip = client[0] if client else "unknown"

        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "/")

        start = time.monotonic()

        structlog.contextvars.clear_contextvars()

        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            client_ip=client_ip,
            method=method,
            path=path,
        )

        async def send_wrapper(message: Message) -> None:

            if message["type"] == "http.response.start":

                headers = list(message.get("headers", []))

                headers.append(
                    (
                        b"x-request-id",
                        request_id.encode(),
                    )
                )

                message["headers"] = headers

            await send(message)

        try:

            logger.debug(
                "request_started"
            )

            await self.app(
                scope,
                receive,
                send_wrapper,
            )

            duration = round(
                time.monotonic() - start,
                4,
            )

            logger.info(
                "request_completed",
                duration=duration,
            )

        except Exception:

            duration = round(
                time.monotonic() - start,
                4,
            )

            logger.exception(
                "request_failed",
                duration=duration,
            )

            raise

        finally:

            structlog.contextvars.clear_contextvars()

    @staticmethod
    def _extract_request_id(
        scope: Scope,
    ) -> str:
        """
        Extract or generate request ID safely.
        """

        try:

            headers = dict(scope.get("headers", []))

            raw_request_id = headers.get(
                REQUEST_ID_HEADER
            )

            if not raw_request_id:
                return str(uuid.uuid4())

            request_id = raw_request_id.decode(
                "utf-8",
                errors="ignore",
            ).strip()

            if (
                not request_id
                or len(request_id)
                > MAX_REQUEST_ID_LENGTH
            ):
                return str(uuid.uuid4())

            return request_id

        except Exception:

            return str(uuid.uuid4())