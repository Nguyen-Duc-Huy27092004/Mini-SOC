"""
DDoS Detection Middleware

Hooks into every incoming HTTP request to:
1. Extract source IP from request headers/client info
2. Record the request in the DDoSEngine sliding window tracker
3. Call evaluate_ip() to detect flood attacks
4. If DDoS detected (confidence >= 85%), auto-block via SOAR FirewallBlock action
5. Return HTTP 429 immediately if source IP is already in blocked list

This middleware is the CRITICAL link between real traffic and the DDoSEngine.
Without it, DDoSEngine.record_request() is never called and no auto-detection occurs.
"""

from __future__ import annotations

import asyncio
import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from starlette.responses import JSONResponse

from app.services.ddos_engine import ddos_engine

logger = structlog.get_logger()

# Paths excluded from DDoS rate tracking (health checks, static assets, etc.)
EXCLUDED_PATHS = {
    "/api/v1/health",
    "/health",
    "/metrics",
    "/favicon.ico",
}


def _extract_client_ip(scope: Scope) -> str:
    """
    Extract real client IP from ASGI scope.
    Respects X-Forwarded-For and X-Real-IP for reverse proxy deployments.
    """
    headers: dict[bytes, bytes] = dict(scope.get("headers", []))

    xff = headers.get(b"x-forwarded-for")
    if xff:
        return xff.decode("utf-8", errors="ignore").split(",")[0].strip()

    x_real_ip = headers.get(b"x-real-ip")
    if x_real_ip:
        return x_real_ip.decode("utf-8", errors="ignore").strip()

    client = scope.get("client")
    if client:
        return client[0]

    return "unknown"


class DDoSMiddleware:
    """
    ASGI middleware that feeds live traffic data into the DDoSEngine.
    Must be added to the FastAPI/Starlette app stack to enable real-time detection.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "/")

        # Skip health checks and excluded paths
        if path in EXCLUDED_PATHS:
            await self.app(scope, receive, send)
            return

        source_ip = _extract_client_ip(scope)

        if source_ip == "unknown":
            await self.app(scope, receive, send)
            return

        # ── Step 1: Check if IP is already blocked ────────────────────────────
        blocked_ips = ddos_engine.get_blocked_ips()
        if source_ip in blocked_ips:
            info = blocked_ips[source_ip]
            logger.warning(
                "ddos_blocked_ip_request_rejected",
                source_ip=source_ip,
                attack_type=info.get("attack_type", "UNKNOWN"),
                path=path,
            )
            response = JSONResponse(
                status_code=429,
                content={
                    "error": "Access Denied",
                    "detail": f"IP {source_ip} is currently blocked by Anti-DDoS firewall.",
                    "attack_type": info.get("attack_type", "UNKNOWN"),
                },
                headers={"Retry-After": "3600"},
            )
            await response(scope, receive, send)
            return

        # ── Step 2: Record this request in sliding window tracker ─────────────
        req_count, rps = ddos_engine.record_request(source_ip)

        # ── Step 3: Evaluate for DDoS if request count exceeds threshold ──────
        # Only evaluate every N requests to avoid per-request async overhead
        should_evaluate = req_count >= ddos_engine.rps_threshold

        if should_evaluate:
            # Fire-and-forget evaluation — do not block the request response
            asyncio.create_task(
                self._evaluate_and_mitigate(source_ip, path, rps)
            )

        await self.app(scope, receive, send)

    async def _evaluate_and_mitigate(self, source_ip: str, path: str, rps: float) -> None:
        """Run DDoS evaluation and auto-mitigation in background."""
        try:
            result = await ddos_engine.evaluate_ip(source_ip, protocol="HTTP")
            if result.is_ddos:
                logger.warning(
                    "ddos_attack_detected_by_middleware",
                    source_ip=source_ip,
                    attack_type=result.attack_type,
                    confidence=result.confidence_score,
                    action=result.action_taken,
                    path=path,
                    rps=rps,
                )
        except Exception:
            logger.exception("ddos_middleware_evaluation_error", source_ip=source_ip)
