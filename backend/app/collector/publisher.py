"""
Enterprise Redis Event Publisher
Production-grade Redis realtime publisher for Mini SOC Portal.
"""

from __future__ import annotations

import asyncio
import json
import time
from contextlib import suppress
from datetime import datetime, timezone
from typing import Optional

import redis.asyncio as aioredis
import structlog
from redis.asyncio.client import Redis

from app.models.event import WazuhEvent

logger = structlog.get_logger()

# =============================================================================
# CHANNELS
# =============================================================================

ALERTS_CHANNEL = "soc:alerts:realtime"
CRITICAL_CHANNEL = "soc:alerts:critical"
METRICS_CHANNEL = "soc:metrics"

# =============================================================================
# CONFIG
# =============================================================================

class PublisherConfig:

    REDIS_URL = "redis://localhost:6379/0"

    MAX_QUEUE_SIZE = 10000

    BATCH_SIZE = 100

    BATCH_TIMEOUT = 0.5

    PUBLISH_TIMEOUT = 3

    RETRY_DELAY = 2

    MAX_PAYLOAD_SIZE = 65536

# =============================================================================
# METRICS
# =============================================================================

class PublisherMetrics:

    published_events = 0

    dropped_events = 0

    publish_failures = 0

    reconnects = 0

    oversized_payloads = 0

    queue_overflows = 0

# =============================================================================
# PUBLISHER
# =============================================================================

class EventPublisher:

    def __init__(
        self,
        redis_url: str = PublisherConfig.REDIS_URL,
    ):

        self.redis_url = redis_url

        self.redis: Optional[Redis] = None

        self.queue: asyncio.Queue = asyncio.Queue(
            maxsize=PublisherConfig.MAX_QUEUE_SIZE
        )

        self._running = False

        self._workers: list[asyncio.Task] = []

        self._circuit_open = False

    # =========================================================================
    # LIFECYCLE
    # =========================================================================

    async def start(self):

        self._running = True

        await self._connect()

        worker = asyncio.create_task(
            self._publisher_worker()
        )

        self._workers.append(worker)

        logger.info(
            "event_publisher_started"
        )

    async def stop(self):

        self._running = False

        for worker in self._workers:
            worker.cancel()

        for worker in self._workers:
            with suppress(asyncio.CancelledError):
                await worker

        await self.close()

        logger.info(
            "event_publisher_stopped"
        )

    # =========================================================================
    # CONNECTION
    # =========================================================================

    async def _connect(self):

        try:

            self.redis = aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                health_check_interval=30,
                retry_on_timeout=True,
            )

            await self.redis.ping()

            logger.info(
                "redis_connected"
            )

        except Exception:

            PublisherMetrics.reconnects += 1

            logger.exception(
                "redis_connection_failed"
            )

            self.redis = None

    async def _ensure_connection(self):

        if self.redis is None:

            await self._connect()

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    async def publish_event(
        self,
        event: WazuhEvent
    ) -> bool:

        if not self._running:
            return False

        try:

            payload = self._serialize(event)

            encoded = json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":")
            )

            if len(encoded) > PublisherConfig.MAX_PAYLOAD_SIZE:

                PublisherMetrics.oversized_payloads += 1

                logger.warning(
                    "payload_too_large",
                    event_id=event.event_id
                )

                return False

            try:

                self.queue.put_nowait(
                    (
                        event.severity,
                        encoded
                    )
                )

                return True

            except asyncio.QueueFull:

                PublisherMetrics.queue_overflows += 1
                PublisherMetrics.dropped_events += 1

                logger.warning(
                    "publisher_queue_full"
                )

                return False

        except Exception:

            logger.exception(
                "publish_enqueue_failed"
            )

            return False

    async def publish_metric(
        self,
        metric_name: str,
        value: float,
        tags: Optional[dict] = None,
    ) -> bool:

        try:

            payload = {
                "name": metric_name,
                "value": value,
                "tags": tags or {},
                "timestamp": self._utcnow_iso(),
            }

            await self._publish_direct(
                METRICS_CHANNEL,
                json.dumps(payload)
            )

            return True

        except Exception:

            logger.exception(
                "metric_publish_failed"
            )

            return False

    # =========================================================================
    # WORKER
    # =========================================================================

    async def _publisher_worker(self):

        logger.info(
            "publisher_worker_started"
        )

        batch = []

        last_flush = time.time()

        while self._running:

            try:

                timeout = (
                    PublisherConfig.BATCH_TIMEOUT
                )

                item = await asyncio.wait_for(
                    self.queue.get(),
                    timeout=timeout
                )

                batch.append(item)

                now = time.time()

                should_flush = (
                    len(batch)
                    >= PublisherConfig.BATCH_SIZE
                    or now - last_flush
                    >= PublisherConfig.BATCH_TIMEOUT
                )

                if should_flush:

                    await self._flush_batch(
                        batch
                    )

                    batch.clear()

                    last_flush = now

            except asyncio.TimeoutError:

                if batch:

                    await self._flush_batch(
                        batch
                    )

                    batch.clear()

            except Exception:

                PublisherMetrics.publish_failures += 1

                logger.exception(
                    "publisher_worker_failed"
                )

                await asyncio.sleep(
                    PublisherConfig.RETRY_DELAY
                )

    # =========================================================================
    # BATCH FLUSH
    # =========================================================================

    async def _flush_batch(
        self,
        batch: list[tuple]
    ):

        if not batch:
            return

        await self._ensure_connection()

        if not self.redis:

            PublisherMetrics.dropped_events += len(batch)

            return

        try:

            pipe = self.redis.pipeline()

            for severity, payload in batch:

                pipe.publish(
                    ALERTS_CHANNEL,
                    payload
                )

                if severity == "critical":

                    pipe.publish(
                        CRITICAL_CHANNEL,
                        payload
                    )

            await asyncio.wait_for(
                pipe.execute(),
                timeout=PublisherConfig.PUBLISH_TIMEOUT
            )

            PublisherMetrics.published_events += len(batch)

            logger.info(
                "batch_published",
                batch_size=len(batch)
            )

        except Exception:

            PublisherMetrics.publish_failures += 1

            logger.exception(
                "batch_publish_failed"
            )

            self.redis = None

    # =========================================================================
    # DIRECT PUBLISH
    # =========================================================================

    async def _publish_direct(
        self,
        channel: str,
        payload: str,
    ):

        await self._ensure_connection()

        if not self.redis:
            return

        try:

            await asyncio.wait_for(
                self.redis.publish(
                    channel,
                    payload
                ),
                timeout=PublisherConfig.PUBLISH_TIMEOUT
            )

        except Exception:

            logger.exception(
                "direct_publish_failed"
            )

            self.redis = None

    # =========================================================================
    # SERIALIZATION
    # =========================================================================

    @staticmethod
    def _serialize(
        event: WazuhEvent
    ) -> dict:

        return {

            "type": "alert",

            "event_id": event.event_id,

            "timestamp": (
                event.event_timestamp.isoformat()
                if event.event_timestamp
                else EventPublisher._utcnow_iso()
            ),

            "severity": event.severity,

            "risk_score": round(
                event.risk_score or 0,
                1
            ),

            "category": event.category,

            "agent": {
                "id": event.agent_id,
                "name": event.agent_name,
            },

            "rule": {
                "id": event.rule_id,
                "description": event.rule_description,
                "level": event.rule_level,
            },

            "message": (
                event.message[:4096]
                if event.message
                else ""
            ),

            "source": {
                "ip": event.source_ip,
                "port": event.source_port,
                "country": event.source_country,
            },

            "destination": {
                "ip": event.dest_ip,
                "port": event.dest_port,
            },

            "suppressed": event.is_suppressed,
        }

    # =========================================================================
    # HEALTH
    # =========================================================================

    def health(self) -> dict:

        return {
            "status": (
                "healthy"
                if self.redis
                else "degraded"
            ),
            "queue_size": self.queue.qsize(),
            "published_events": (
                PublisherMetrics.published_events
            ),
            "publish_failures": (
                PublisherMetrics.publish_failures
            ),
            "dropped_events": (
                PublisherMetrics.dropped_events
            ),
        }

    # =========================================================================
    # CLOSE
    # =========================================================================

    async def close(self):

        if self.redis:

            await self.redis.close()

            self.redis = None

    # =========================================================================
    # UTILS
    # =========================================================================

    @staticmethod
    def _utcnow_iso():

        return datetime.now(
            timezone.utc
        ).isoformat()