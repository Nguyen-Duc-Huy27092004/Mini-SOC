import abc
from typing import Any, Dict
import structlog
import traceback

logger = structlog.get_logger()

class ActionResult:
    def __init__(self, success: bool, message: str, response_payload: Dict[str, Any] = None):
        self.success = success
        self.message = message
        self.response_payload = response_payload or {}

class BaseAction(abc.ABC):
    """
    Abstract base class for all SOAR Actions.
    """
    @abc.abstractmethod
    async def execute(self, config: Dict[str, Any], trigger_data: Dict[str, Any]) -> ActionResult:
        pass

# ---------------------------------------------------------
# Action Implementations
# ---------------------------------------------------------

class WebhookAction(BaseAction):
    async def execute(self, config: Dict[str, Any], trigger_data: Dict[str, Any]) -> ActionResult:
        url = config.get("url")
        if not url:
            return ActionResult(False, "Webhook URL not configured")
        
        import httpx
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json={"trigger": trigger_data, "config": config})
                response.raise_for_status()
                return ActionResult(True, f"Webhook sent successfully: {response.status_code}", {"status": response.status_code})
        except Exception as e:
            return ActionResult(False, f"Webhook failed: {str(e)}", {"error": str(e), "traceback": traceback.format_exc()})


class LogAction(BaseAction):
    async def execute(self, config: Dict[str, Any], trigger_data: Dict[str, Any]) -> ActionResult:
        message = config.get("message", "SOAR Action Log executed")
        logger.info("soar_log_action", message=message, trigger_data=trigger_data)
        return ActionResult(True, "Logged successfully", {"message": message})


# Add more actions (Email, Telegram, etc.) by subclassing BaseAction

# ---------------------------------------------------------
# Action Engine Factory
# ---------------------------------------------------------

class ActionEngine:
    _actions = {
        "webhook": WebhookAction(),
        "log": LogAction(),
    }

    @classmethod
    def register_action(cls, name: str, action_instance: BaseAction):
        cls._actions[name] = action_instance

    @classmethod
    async def execute_action(cls, action_type: str, config: Dict[str, Any], trigger_data: Dict[str, Any]) -> ActionResult:
        action = cls._actions.get(action_type.lower())
        if not action:
            return ActionResult(False, f"Unsupported action type: {action_type}")
        
        try:
            return await action.execute(config, trigger_data)
        except Exception as e:
            logger.exception("soar_action_unhandled_error", action_type=action_type)
            return ActionResult(False, f"Unhandled error in action {action_type}: {str(e)}", {"traceback": traceback.format_exc()})
