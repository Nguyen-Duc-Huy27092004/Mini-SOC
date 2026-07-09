import asyncio
import structlog
from app.core.config import settings
from app.core.logging import setup_logging
from app.collector import start_collector
from app.core.redis_client import close_redis

logger = structlog.get_logger()

async def main():
    """
    Dedicated worker entrypoint for Wazuh Alerts Collector.
    Decoupled from FastAPI backend to allow horizontal scaling of the web server
    without duplicating file tailing.
    """
    setup_logging()
    await logger.ainfo("collector_worker_starting", env=settings.ENV)

    collector_task = asyncio.create_task(start_collector())

    try:
        # Keep worker alive
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        await logger.ainfo("collector_worker_shutting_down")
    finally:
        collector_task.cancel()
        try:
            await asyncio.wait_for(asyncio.gather(collector_task, return_exceptions=True), timeout=5.0)
        except asyncio.TimeoutError:
            pass
        await close_redis()
        await logger.ainfo("collector_worker_stopped")

if __name__ == "__main__":
    asyncio.run(main())
