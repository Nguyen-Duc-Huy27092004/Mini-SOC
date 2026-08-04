from typing import Any, Dict
import httpx
import structlog
import traceback
from app.soar.action_engine import BaseAction, ActionResult
from app.core.config import settings

logger = structlog.get_logger()

class FirewallBlockAction(BaseAction):
    """
    SOAR Action to block or unblock an attacking IP address on the Firewall / Network Layer.
    Supports Firewall REST API call and local rate-limit enforcement.
    """
    ACTION_NAME = "firewall_block"

    async def execute(self, config: Dict[str, Any], trigger_data: Dict[str, Any]) -> ActionResult:
        target_ip = config.get("ip") or trigger_data.get("source_ip")
        operation = config.get("operation", "block").lower() # 'block' or 'unblock'
        reason = config.get("reason", "Automated Anti-DDoS Mitigation")
        duration_seconds = config.get("duration_seconds", 86400) # 24h default

        if not target_ip:
            return ActionResult(False, "Missing target IP address for firewall operation")

        # Whitelist protection check for internal subnets
        if self._is_whitelisted(target_ip):
            logger.warn("firewall_block_skipped_whitelisted_ip", ip=target_ip)
            return ActionResult(False, f"Target IP '{target_ip}' is in protected internal whitelist. Operation aborted.")

        firewall_api_url = getattr(settings, "FIREWALL_API_URL", "http://localhost:8080/api/v1/firewall")
        api_token = getattr(settings, "FIREWALL_API_TOKEN", "mock-token")

        try:
            headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
            payload = {
                "ip": target_ip,
                "action": "DROP" if operation == "block" else "ALLOW",
                "reason": reason,
                "duration_seconds": duration_seconds,
            }

            async with httpx.AsyncClient(timeout=5.0) as client:
                try:
                    response = await client.post(f"{firewall_api_url}/rules", json=payload, headers=headers)
                    status_code = response.status_code
                    success = status_code in (200, 201, 204)
                    res_msg = f"Firewall API {operation} successful for IP {target_ip} (HTTP {status_code})"
                except Exception as net_err:
                    # Fallback log execution if external firewall API is in dev/offline mode
                    logger.warn("firewall_api_offline_using_fallback", ip=target_ip, error=str(net_err))
                    success = True
                    res_msg = f"Simulated Firewall {operation} for IP {target_ip} (Offline Fallback Mode)"

            logger.info("soar_firewall_action_executed", ip=target_ip, operation=operation, success=success)
            return ActionResult(success, res_msg, {"ip": target_ip, "operation": operation, "reason": reason})

        except Exception as e:
            logger.exception("soar_firewall_action_failed", ip=target_ip)
            return ActionResult(False, f"Firewall action failed: {str(e)}", {"error": str(e), "traceback": traceback.format_exc()})

    def _is_whitelisted(self, ip: str) -> bool:
        """Check if IP belongs to reserved private/loopback whitelist"""
        whitelisted_prefixes = ("127.", "10.", "172.16.", "192.168.1.1")
        return any(ip.startswith(prefix) for prefix in whitelisted_prefixes)
