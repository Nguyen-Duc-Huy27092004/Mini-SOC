from typing import Any, Dict

import structlog
from fastapi import APIRouter, HTTPException, Request, status

from app.collector.service import get_collector

router = APIRouter()
logger = structlog.get_logger()

@router.post(
    "/webhook",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Receive alert webhook from Wazuh Manager",
    tags=["Wazuh"],
)
async def wazuh_webhook(request: Request) -> Dict[str, Any]:
    """
    Receives alerts directly from Wazuh Manager's custom webhook integration.
    """
    try:
        raw_alert = await request.json()
    except Exception as exc:
        logger.warning("wazuh_webhook_invalid_json", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        )

    collector = get_collector()
    success = collector.enqueue_alert(raw_alert)

    if not success:
        logger.warning("wazuh_webhook_queue_full_or_stopped")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Collector queue is full or not running",
        )

    return {"status": "ok", "message": "Alert enqueued successfully"}
