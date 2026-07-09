from typing import Any, Dict
import httpx
import traceback
from app.soar.action_engine import BaseAction, ActionResult
from app.core.security.validators import validate_safe_url, SSRFVulnerabilityError

class WebhookAction(BaseAction):
    
    ACTION_NAME = "webhook"
    
    async def execute(self, config: Dict[str, Any], trigger_data: Dict[str, Any]) -> ActionResult:
        url = config.get("url")
        if not url:
            return ActionResult(False, "Webhook URL not configured")
        
        try:
            # Validate URL to prevent SSRF
            safe_url = validate_safe_url(url)
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(safe_url, json={"trigger": trigger_data, "config": config})
                response.raise_for_status()
                return ActionResult(True, f"Webhook sent successfully: {response.status_code}", {"status": response.status_code})
                
        except SSRFVulnerabilityError as e:
            return ActionResult(False, f"Security Error: {str(e)}")
        except Exception as e:
            return ActionResult(False, f"Webhook failed: {str(e)}", {"error": str(e), "traceback": traceback.format_exc()})
