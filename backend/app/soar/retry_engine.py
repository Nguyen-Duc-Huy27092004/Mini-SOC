import asyncio
from typing import Callable, Any
import structlog

logger = structlog.get_logger()

class RetryEngine:
    @staticmethod
    async def execute_with_retry(
        func: Callable,
        max_retries: int = 3,
        base_delay: float = 1.0,
        *args,
        **kwargs
    ) -> Any:
        """
        Executes a function with exponential backoff retry logic.
        """
        retries = 0
        while True:
            try:
                result = await func(*args, **kwargs)
                if hasattr(result, "success") and not result.success:
                    # Treat action failure (e.g. ActionResult with success=False) as a reason to retry
                    if retries >= max_retries:
                        return result
                    raise Exception(result.message)
                return result
            except Exception as e:
                if retries >= max_retries:
                    logger.error("soar_retry_exhausted", func=func.__name__, retries=retries, error=str(e))
                    # Return the last result if it's an ActionResult, else re-raise or return failure
                    return result if 'result' in locals() and hasattr(result, "success") else None
                
                retries += 1
                delay = base_delay * (2 ** (retries - 1)) # Exponential backoff
                logger.warning("soar_action_retry", func=func.__name__, retry=retries, delay=delay, error=str(e))
                await asyncio.sleep(delay)
