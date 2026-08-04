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

    try:
        await start_collector()
    except asyncio.CancelledError:
        await logger.ainfo("collector_worker_shutting_down")
    except Exception as exc:
        await logger.aerror("collector_worker_crashed", error=str(exc), exc_info=True)
        raise
    finally:
        await close_redis()
        await logger.ainfo("collector_worker_stopped")

if __name__ == "__main__":
    asyncio.run(main())
