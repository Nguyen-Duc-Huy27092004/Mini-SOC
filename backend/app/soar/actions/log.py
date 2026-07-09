from typing import Any, Dict
import structlog
from app.soar.action_engine import BaseAction, ActionResult

logger = structlog.get_logger()

class LogAction(BaseAction):
    
    ACTION_NAME = "log"
    
    async def execute(self, config: Dict[str, Any], trigger_data: Dict[str, Any]) -> ActionResult:
        message = config.get("message", "SOAR Action Log executed")
        logger.info("soar_log_action", message=message, trigger_data=trigger_data)
        return ActionResult(True, "Logged successfully", {"message": message})
