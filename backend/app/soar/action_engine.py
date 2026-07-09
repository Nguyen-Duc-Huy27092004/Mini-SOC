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

import pkgutil
import importlib
import inspect

class ActionEngine:
    _actions = {}
    _plugins_loaded = False

    @classmethod
    def _load_plugins(cls):
        if cls._plugins_loaded:
            return
            
        import app.soar.actions as actions_pkg
        
        for _, name, _ in pkgutil.iter_modules(actions_pkg.__path__):
            module = importlib.import_module(f"app.soar.actions.{name}")
            for item_name, item in inspect.getmembers(module):
                if inspect.isclass(item) and issubclass(item, BaseAction) and item is not BaseAction:
                    action_name = getattr(item, "ACTION_NAME", name.lower())
                    cls.register_action(action_name, item())
                    
        cls._plugins_loaded = True
        logger.info("soar_action_plugins_loaded", count=len(cls._actions))

    @classmethod
    def register_action(cls, name: str, action_instance: BaseAction):
        cls._actions[name] = action_instance

    @classmethod
    async def execute_action(cls, action_type: str, config: Dict[str, Any], trigger_data: Dict[str, Any]) -> ActionResult:
        cls._load_plugins()
        action = cls._actions.get(action_type.lower())
        if not action:
            return ActionResult(False, f"Unsupported action type: {action_type}")
        
        try:
            return await action.execute(config, trigger_data)
        except Exception as e:
            logger.exception("soar_action_unhandled_error", action_type=action_type)
            return ActionResult(False, f"Unhandled error in action {action_type}: {str(e)}", {"traceback": traceback.format_exc()})
