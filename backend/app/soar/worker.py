import asyncio
import json
import structlog
from app.core.redis import get_redis_manager
from app.core.database import async_session_maker
from app.soar.playbook_engine import PlaybookEngine
from sqlalchemy import select
from app.models.zabbix import ZabbixProblem
from app.soar.scheduler import SoarScheduler

logger = structlog.get_logger()

class SoarWorker:
    def __init__(self):
        self.redis = get_redis_manager()
        self.is_running = False
        self._tasks = []

    async def start(self):
        """Starts the SOAR background worker."""
        logger.info("soar_worker_starting")
        self.is_running = True

        # Start persistent scheduler
        SoarScheduler.start()

        try:
            await self.redis.initialize()
        except Exception as e:
            logger.warning("soar_redis_unavailable", error=str(e))

        self._tasks.append(asyncio.create_task(self._subscribe_to_wazuh_alerts()))
        self._tasks.append(asyncio.create_task(self._poll_zabbix_problems()))

    async def stop(self):
        """Stops the worker."""
        logger.info("soar_worker_stopping")
        self.is_running = False
        SoarScheduler.stop()
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def _subscribe_to_wazuh_alerts(self):
        """Listens to real-time Wazuh alerts over Redis pub/sub."""
        try:
            if self.redis.client is None:
                await self.redis.initialize()
        except Exception as e:
            logger.warning("soar_wazuh_subscribe_skipped", error=str(e))
            return

        pubsub = self.redis.client.pubsub()
        await pubsub.subscribe("soc:alerts:realtime")

        logger.info("soar_subscribed_to_wazuh")
        try:
            while self.is_running:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        async with async_session_maker() as session:
                            engine = PlaybookEngine(session)
                            await engine.process_trigger(trigger_source="wazuh", trigger_data=data)
                    except Exception as e:
                        logger.error("soar_wazuh_event_error", error=str(e))
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe("soc:alerts:realtime")

    async def _poll_zabbix_problems(self):
        """Polls PostgreSQL for new Zabbix problems periodically."""
        # Simple polling approach - in production a CDC or pub/sub from zabbix_service would be better,
        # but to avoid touching old code, we poll for recent problems.
        last_checked_id = 0
        poll_interval = 10 # seconds

        logger.info("soar_started_zabbix_polling")
        try:
            if self.redis.client is None:
                try:
                    await self.redis.initialize()
                except Exception as e:
                    logger.warning("soar_redis_unavailable", error=str(e))
                    await asyncio.sleep(poll_interval)
                    return

            # We use the raw aioredis client
            redis_client = self.redis.client

            while self.is_running:
                try:
                    # 1. Acquire Distributed Lock (timeout 5s so if crashed, it releases quickly)
                    async with redis_client.lock("soar:zabbix_poller_lock", timeout=5.0, blocking_timeout=1.0) as lock:
                        if not lock:
                            continue # Could not acquire lock, another instance is polling
                            
                        async with async_session_maker() as session:
                            # Fetch recent unresolved problems we haven't seen
                            # Since UUIDs aren't strictly ordered integers, we can use clock_id or created_at
                            # For simplicity, we just fetch problems created in the last 15 seconds
                            import datetime
                            recent_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=poll_interval + 5)

                            stmt = select(ZabbixProblem).where(ZabbixProblem.created_at >= recent_time)
                            result = await session.execute(stmt)
                            problems = result.scalars().all()

                            for prob in problems:
                                # Convert to dict for trigger data
                                prob_data = {
                                    "problem_id": prob.problem_id,
                                    "name": prob.name,
                                    "severity": prob.severity,
                                    "status": prob.status
                                }
                                # Simple deduplication via Redis SETNX
                                dedup_key = f"soar:zabbix_dedup:{prob.problem_id}"
                                is_new = await redis_client.setnx(dedup_key, "1")
                                if is_new:
                                    # Expire after 30 days to keep redis clean
                                    await redis_client.expire(dedup_key, 2592000)
                                    engine = PlaybookEngine(session)
                                    await engine.process_trigger(trigger_source="zabbix", trigger_data=prob_data)
                                else:
                                    logger.debug("soar_zabbix_problem_duplicate", problem_id=prob.problem_id)
                except asyncio.TimeoutError:
                    # Could not acquire lock, skip this interval
                    pass
                except Exception as e:
                    if "LockError" in str(type(e)):
                        pass
                    else:
                        logger.error("soar_zabbix_poll_error", error=str(e))
                
                await asyncio.sleep(poll_interval)
        except asyncio.CancelledError:
            pass
