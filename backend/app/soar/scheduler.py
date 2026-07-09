import asyncio
import datetime
import structlog
from typing import Callable, Any, Coroutine

logger = structlog.get_logger()

class SoarScheduler:
    """
    A lightweight scheduler to handle Immediate, Delay, and Cron executions.
    """

    @staticmethod
    async def schedule_immediate(func: Callable[..., Coroutine[Any, Any, Any]], *args, **kwargs):
        """Run immediately in the background."""
        asyncio.create_task(func(*args, **kwargs))

    @staticmethod
    async def schedule_delay(delay_seconds: int, func: Callable[..., Coroutine[Any, Any, Any]], *args, **kwargs):
        """Run after a delay."""
        async def _delayed_task():
            logger.info("soar_task_delayed", delay=delay_seconds)
            await asyncio.sleep(delay_seconds)
            await func(*args, **kwargs)
        
        asyncio.create_task(_delayed_task())

    @staticmethod
    async def schedule_cron(cron_expr: str, func: Callable[..., Coroutine[Any, Any, Any]], *args, **kwargs):
        """
        A simplified cron scheduler. (e.g. '* * * * *' for every minute)
        For a production system, APScheduler or Celery Beat is recommended.
        This provides a minimal implementation without adding external dependencies.
        """
        logger.warning("soar_cron_scheduled", cron=cron_expr, note="Minimal implementation. Only supports simple * or exact numbers.")
        
        async def _cron_task():
            while True:
                now = datetime.datetime.now()
                # Parse basic cron: min hour day month dow
                parts = cron_expr.split()
                if len(parts) == 5:
                    c_min, c_hr, c_day, c_mon, c_dow = parts
                    
                    match_min = c_min == '*' or str(now.minute) == c_min
                    match_hr = c_hr == '*' or str(now.hour) == c_hr
                    match_day = c_day == '*' or str(now.day) == c_day
                    match_mon = c_mon == '*' or str(now.month) == c_mon
                    match_dow = c_dow == '*' or str(now.isoweekday() % 7) == c_dow # 0=Sunday in cron typically

                    if match_min and match_hr and match_day and match_mon and match_dow:
                        logger.info("soar_cron_triggered", cron=cron_expr)
                        # Fire and wait a minute so it doesn't trigger multiple times in the same minute
                        asyncio.create_task(func(*args, **kwargs))
                        await asyncio.sleep(61)
                        continue
                
                # Check every 30 seconds
                await asyncio.sleep(30)
                
        asyncio.create_task(_cron_task())
