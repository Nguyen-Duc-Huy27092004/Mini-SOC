from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Optional

import structlog

from app.collector.alerts_tail import AlertsFileTailer, CollectorConfig
from app.collector.event_normalizer import EventNormalizer, EventRouter
from app.collector.publisher import EventPublisher
from app.core.config import settings
from app.core.database import async_session_maker
from app.integrations.wazuh_client import WazuhAPIClient
from app.services.alert_suppression import AlertSuppressionService
from app.services.geoip import GeoIPService
from app.services.risk_scoring import RiskScoreService

logger = structlog.get_logger()


class AlertsCollectorService:
    """
    Production-grade realtime Wazuh collector.
    """

    def __init__(self) -> None:

        self.alerts_file = settings.WAZUH_ALERTS_FILE
        self.redis_url = settings.REDIS_URL

        self.queue: asyncio.Queue = asyncio.Queue(maxsize=5000)

        self.worker_count = 4
        self.workers: list[asyncio.Task] = []

        self._is_running = False

        self._processed_count = 0
        self._error_count = 0
        self._dropped_count = 0

        self._tail_task: Optional[asyncio.Task] = None

        # Fix: AlertsFileTailer only takes config, not alerts_file
        # alerts_file is auto-detected inside the class
        self.tailer = AlertsFileTailer(
            config=CollectorConfig(),
        )

        self.publisher = EventPublisher(
            redis_url=self.redis_url
        )

        self.geoip_service = GeoIPService(
            db_path=settings.GEOIP_DB_PATH,
            redis_url=self.redis_url,
        )

        self.normalizer = EventNormalizer(
            geoip_service=self.geoip_service
        )

        self.router = EventRouter(
            suppression_service=AlertSuppressionService(),
            risk_service=RiskScoreService(),
            publisher=self.publisher,
        )

        self.wazuh_client = WazuhAPIClient(
            base_url=settings.WAZUH_API_URL,
            username=settings.WAZUH_API_USER,
            password=settings.WAZUH_API_PASSWORD.get_secret_value(),
            verify_ssl=settings.WAZUH_VERIFY_SSL,
        )

    # =========================================================
    # STARTUP
    # =========================================================

    async def start(self) -> None:

        if self._is_running:
            return

        self._is_running = True

        await logger.ainfo(
            "collector_starting",
            workers=self.worker_count,
        )

        self._tail_task = asyncio.create_task(
            self._tail_loop()
        )

        for idx in range(self.worker_count):
            task = asyncio.create_task(
                self._worker_loop(idx)
            )
            self.workers.append(task)

        await logger.ainfo("collector_started")

    # =========================================================
    # TAIL LOOP
    # =========================================================

    async def _tail_loop(self) -> None:

        try:
            async for raw_alert in self.tailer.tail():

                if not self._is_running:
                    break

                try:
                    self.queue.put_nowait(raw_alert)

                except asyncio.QueueFull:

                    self._dropped_count += 1

                    await logger.awarning(
                        "collector_queue_full",
                        dropped=self._dropped_count,
                        queue_size=self.queue.qsize(),
                    )

        except asyncio.CancelledError:
            pass

        except Exception:
            self._error_count += 1

            await logger.aerror(
                "collector_tail_loop_error",
                exc_info=True,
            )

    # =========================================================
    # WORKERS
    # =========================================================

    async def _worker_loop(self, worker_id: int) -> None:

        await logger.ainfo(
            "collector_worker_started",
            worker_id=worker_id,
        )

        while self._is_running:

            try:
                raw_alert = await asyncio.wait_for(
                    self.queue.get(),
                    timeout=2.0,
                )

            except asyncio.TimeoutError:
                continue

            except asyncio.CancelledError:
                break

            try:
                await self._process_event(raw_alert)

            except Exception:
                self._error_count += 1

                await logger.aerror(
                    "collector_worker_error",
                    worker_id=worker_id,
                    exc_info=True,
                )

            finally:
                self.queue.task_done()

    # =========================================================
    # EVENT PROCESSING
    # =========================================================

    async def _process_event(self, raw_alert: dict) -> None:

        async with async_session_maker() as db:

            event = await asyncio.wait_for(
                self.normalizer.normalize(raw_alert),
                timeout=5.0,
            )

            if not event:
                return

            published = await asyncio.wait_for(
                self.router.route_event(event, db),
                timeout=10.0,
            )

            if published:
                self._processed_count += 1

                if self._processed_count % 500 == 0:

                    await logger.ainfo(
                        "collector_stats",
                        processed=self._processed_count,
                        errors=self._error_count,
                        dropped=self._dropped_count,
                        queue_size=self.queue.qsize(),
                    )

    # =========================================================
    # INVENTORY SYNC
    # =========================================================

    async def sync_endpoint_inventory(self) -> int:

        try:
            agents = await asyncio.wait_for(
                self.wazuh_client.get_agents(),
                timeout=20.0,
            )

            if not agents:
                await logger.awarning(
                    "inventory_sync_no_agents",
                    reason="wazuh_api_returned_empty",
                )
                return 0

            from sqlalchemy import select
            from app.models.event import EndpointInventory

            count = 0

            async with async_session_maker() as db:

                for agent_data in agents:

                    agent_id = str(
                        agent_data.get("id", "000")
                    ).zfill(3)

                    existing = await db.scalar(
                        select(EndpointInventory).where(
                            EndpointInventory.agent_id == agent_id
                        )
                    )

                    if existing:

                        existing.agent_name = agent_data.get(
                            "name",
                            existing.agent_name,
                        )

                        existing.status = agent_data.get(
                            "status",
                            "unknown",
                        )

                    else:

                        db.add(
                            EndpointInventory(
                                agent_id=agent_id,
                                agent_name=agent_data.get(
                                    "name",
                                    "unknown",
                                ),
                                status=agent_data.get(
                                    "status",
                                    "unknown",
                                ),
                            )
                        )

                    count += 1

                await db.commit()

            await logger.ainfo(
                "inventory_sync_complete",
                agents_synced=count,
            )

            return count

        except asyncio.TimeoutError:

            await logger.aerror(
                "inventory_sync_timeout",
                timeout_seconds=20,
            )

            return 0

        except Exception:

            await logger.aerror(
                "inventory_sync_error",
                exc_info=True,
            )

            return 0

    # =========================================================
    # SHUTDOWN
    # =========================================================

    async def stop(self) -> None:

        if not self._is_running:
            return

        self._is_running = False

        await logger.ainfo("collector_stopping")

        if self._tail_task:
            self._tail_task.cancel()

            with suppress(asyncio.CancelledError):
                await self._tail_task

        for task in self.workers:
            task.cancel()

        for task in self.workers:
            with suppress(asyncio.CancelledError):
                await task

        await self.publisher.close()

        await self.geoip_service.close()

        await self.wazuh_client.close()

        await logger.ainfo(
            "collector_stopped",
            processed=self._processed_count,
            errors=self._error_count,
            dropped=self._dropped_count,
        )

    # =========================================================
    # HEALTH
    # =========================================================

    def get_stats(self) -> dict:

        return {
            "running": self._is_running,
            "processed": self._processed_count,
            "errors": self._error_count,
            "dropped": self._dropped_count,
            "queue_size": self.queue.qsize(),
            "workers": len(self.workers),
        }


_collector: Optional[AlertsCollectorService] = None


def get_collector() -> AlertsCollectorService:

    global _collector

    if _collector is None:
        _collector = AlertsCollectorService()

    return _collector


async def start_collector() -> None:
    """
    Boot-safe collector loop: retries until Wazuh alerts file is available.
    Never crashes the API process.
    """
    collector = get_collector()
    retry_delay = 5.0

    while True:
        try:
            if not settings.WAZUH_ALERTS_FILE:
                await logger.awarning(
                    "collector_disabled",
                    reason="WAZUH_ALERTS_FILE not configured",
                )
                await asyncio.sleep(30.0)
                continue

            from pathlib import Path

            alerts_path = Path(settings.WAZUH_ALERTS_FILE)
            if not alerts_path.exists():
                await logger.awarning(
                    "collector_waiting_for_alerts_file",
                    path=str(alerts_path),
                )
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 1.5, 60.0)
                continue

            retry_delay = 5.0
            await collector.start()
            # start() runs until cancelled or tail loop exits
            await asyncio.sleep(5.0)
        except asyncio.CancelledError:
            await collector.stop()
            break
        except Exception:
            await logger.aerror("collector_restart_loop_error", exc_info=True)
            await collector.stop()
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 120.0)