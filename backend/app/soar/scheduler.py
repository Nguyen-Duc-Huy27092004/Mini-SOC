import structlog
import asyncio
from datetime import datetime, timedelta
from typing import Callable, Any, Coroutine
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.triggers.cron import CronTrigger
from app.core.config import settings

logger = structlog.get_logger()

# We use Redis for the job store (APScheduler handles persistence)
jobstores = {
    'default': RedisJobStore(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD.get_secret_value() if settings.REDIS_PASSWORD else None,
        db=1, # Use a different DB or just default
        jobs_key='soar_jobs',
        run_times_key='soar_run_times'
    )
}


scheduler = AsyncIOScheduler(jobstores=jobstores, timezone="UTC")

class SoarScheduler:
    """
    Persistent scheduler using APScheduler backed by Redis.
    Handles Immediate, Delay, and Cron executions reliably even after restarts.
    """
    
    @classmethod
    def start(cls):
        if not scheduler.running:
            scheduler.start()
            logger.info("soar_scheduler_started")

    @classmethod
    def stop(cls):
        if scheduler.running:
            scheduler.shutdown(wait=False)
            logger.info("soar_scheduler_stopped")

    @staticmethod
    def schedule_immediate(func: Callable[..., Coroutine[Any, Any, Any]], *args, **kwargs):
        """Run immediately in the background without persistence."""
        asyncio.create_task(func(*args, **kwargs))

    @staticmethod
    def schedule_delay(delay_seconds: int, func: Callable[..., Coroutine[Any, Any, Any]], *args, **kwargs):
        """Run after a delay (Persistent)."""
        run_date = datetime.now() + timedelta(seconds=delay_seconds)
        scheduler.add_job(
            func,
            'date',
            run_date=run_date,
            args=args,
            kwargs=kwargs,
            misfire_grace_time=3600 # 1 hour grace
        )
        logger.info("soar_task_delayed", delay=delay_seconds)

    @staticmethod
    def schedule_cron(cron_expr: str, func: Callable[..., Coroutine[Any, Any, Any]], *args, **kwargs):
        """Run on a cron schedule."""
        parts = cron_expr.split()
        if len(parts) == 5:
            trigger = CronTrigger(
                minute=parts[0],
                hour=parts[1],
                day=parts[2],
                month=parts[3],
                day_of_week=parts[4]
            )
            scheduler.add_job(
                func,
                trigger,
                args=args,
                kwargs=kwargs,
                misfire_grace_time=3600
            )
            logger.info("soar_cron_scheduled", cron=cron_expr)
        else:
            logger.error("invalid_cron_expression", cron=cron_expr)
