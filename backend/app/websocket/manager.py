"""Redis-backed WebSocket fan-out with role-filtered delivery (multi-worker safe)."""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

import redis.asyncio as aioredis
import structlog
from fastapi import WebSocket

from app.core.config import settings

logger = structlog.get_logger()

# Must match publisher.py constants
ALERTS_CHANNEL = "soc:alerts:realtime"
WS_CONTROL_CHANNEL = "soc:ws:control"


@dataclass
class WsClient:
    websocket: WebSocket
    user_id: str
    roles: Set[str] = field(default_factory=set)


def _roles_may_receive_alert(roles: Set[str], alert: dict) -> bool:
    """SOC Analyst+ see all; Manager/Auditor see high+ only."""
    if roles & {"Super Admin", "SOC Analyst", "IT Admin"}:
        return True
    severity = alert.get("severity", "low")
    if roles & {"Manager", "Auditor"}:
        return severity in ("critical", "high")
    return False


class ConnectionManager:
    def __init__(self) -> None:
        self._clients: Dict[int, WsClient] = {}
        self._redis: Optional[aioredis.Redis] = None
        self._pubsub_task: Optional[asyncio.Task] = None
        self._client_id = 0

    async def connect(self, websocket: WebSocket, user_id: str, roles: List[str]) -> int:
        await websocket.accept()
        self._client_id += 1
        cid = self._client_id
        self._clients[cid] = WsClient(
            websocket=websocket,
            user_id=user_id,
            roles=set(roles),
        )
        await logger.ainfo("ws_connected", user_id=user_id, active=len(self._clients))
        return cid

    def disconnect(self, client_id: int) -> None:
        self._clients.pop(client_id, None)
        logger.info("ws_disconnected", active=len(self._clients))

    def active_connections(self) -> int:
        return len(self._clients)

    async def _send_to_client(self, client: WsClient, payload: str) -> bool:
        try:
            await client.websocket.send_text(payload)
            return True
        except Exception:
            return False

    async def broadcast_alert(self, alert: dict) -> None:
        """Broadcast alert to eligible connected clients."""
        payload = json.dumps(alert)
        dead: List[int] = []
        for cid, client in list(self._clients.items()):
            if not _roles_may_receive_alert(client.roles, alert):
                continue
            if not await self._send_to_client(client, payload):
                dead.append(cid)
        for cid in dead:
            self.disconnect(cid)

    async def check_ws_rate(self, user_id: str) -> bool:
        """Rate-limit WebSocket connections per user."""
        if self._redis is None:
            self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        key = f"ws:rate:{user_id}"
        count = await self._redis.incr(key)
        if count == 1:
            await self._redis.expire(key, 60)
        return count <= settings.WS_RATE_LIMIT_PER_MINUTE

    async def start_redis_listener(self) -> None:
        """Subscribe to Redis Pub/Sub and fan out to WebSocket clients."""
        self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(ALERTS_CHANNEL)
        await logger.ainfo("redis_pubsub_subscribed", channel=ALERTS_CHANNEL)

        while True:
            try:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message and message.get("data"):
                    try:
                        data = json.loads(message["data"])
                        await self.broadcast_alert(data)
                    except (json.JSONDecodeError, Exception) as exc:
                        await logger.awarning("ws_broadcast_parse_error", error=str(exc))
            except asyncio.CancelledError:
                await pubsub.unsubscribe(ALERTS_CHANNEL)
                break
            except Exception as exc:
                await logger.aerror("redis_pubsub_error", error=str(exc))
                await asyncio.sleep(2.0)

    def start_listener_task(self) -> None:
        self._pubsub_task = asyncio.create_task(self.start_redis_listener())

    def stop_listener_task(self) -> None:
        if self._pubsub_task:
            self._pubsub_task.cancel()


manager = ConnectionManager()
