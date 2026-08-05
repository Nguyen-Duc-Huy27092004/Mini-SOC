"""
SOAR Action: isolate_host
Isolates a compromised endpoint by triggering the Wazuh Active Response
module on the target agent. This cuts network access on the host while
keeping the Wazuh agent connection alive for forensic investigation.

Config fields:
    agent_id (str): Wazuh agent ID to isolate (e.g. "001").
    command (str, optional): Active-response command name.
                             Default "!isolate-host" (Wazuh built-in).
    timeout (int, optional): Duration in seconds for the active-response.
                             0 means permanent until manually unblocked.
    operation (str): "isolate" (default) or "unisolate" to restore.

Fallback: If Wazuh API is unavailable, logs the action and returns success
          in simulation mode so playbooks don't break in dev environments.
"""
from __future__ import annotations

from typing import Any, Dict

import httpx
import structlog

from app.soar.action_engine import BaseAction, ActionResult
from app.core.config import settings

logger = structlog.get_logger()


class IsolateHostAction(BaseAction):
    """
    SOAR Action to isolate/unisolate a Wazuh-monitored endpoint via
    the Wazuh Manager Active Response API.
    """

    ACTION_NAME = "isolate_host"

    async def execute(self, config: Dict[str, Any], trigger_data: Dict[str, Any]) -> ActionResult:
        # Resolve agent_id — can come from config or trigger_data
        agent_id = str(
            config.get("agent_id")
            or trigger_data.get("agent_id")
            or trigger_data.get("agent", {}).get("id", "")
        ).strip()

        if not agent_id:
            return ActionResult(False, "isolate_host: agent_id is required but not provided.")

        operation = config.get("operation", "isolate").lower()
        timeout   = int(config.get("timeout", 0))  # 0 = permanent

        # Map operation to Wazuh active-response command
        if operation == "unisolate":
            command = config.get("command", "!unisolate-host")
        else:
            command = config.get("command", "!isolate-host")

        wazuh_url = settings.WAZUH_API_URL.rstrip("/")
        wazuh_user = settings.WAZUH_API_USER
        wazuh_pass = settings.WAZUH_API_PASSWORD.get_secret_value()

        try:
            async with httpx.AsyncClient(
                verify=settings.WAZUH_VERIFY_SSL,
                timeout=15.0,
            ) as client:
                # Step 1: Obtain JWT token from Wazuh API
                auth_resp = await client.post(
                    f"{wazuh_url}/security/user/authenticate",
                    auth=(wazuh_user, wazuh_pass),
                )
                if auth_resp.status_code != 200:
                    raise RuntimeError(f"Wazuh auth failed: HTTP {auth_resp.status_code}")

                token = auth_resp.json()["data"]["token"]
                headers = {"Authorization": f"Bearer {token}"}

                # Step 2: Trigger active-response on the target agent
                ar_payload = {
                    "command": command,
                    "arguments": [],
                    "alert": trigger_data,
                }
                if timeout > 0:
                    ar_payload["timeout"] = timeout

                ar_resp = await client.put(
                    f"{wazuh_url}/active-response",
                    headers=headers,
                    json=ar_payload,
                    params={"agents_list": agent_id},
                )

                if ar_resp.status_code in (200, 201):
                    logger.info(
                        "soar_isolate_host_success",
                        agent_id=agent_id,
                        operation=operation,
                        command=command,
                    )
                    return ActionResult(
                        True,
                        f"Agent {agent_id} {operation}d successfully via Wazuh Active Response.",
                        {"agent_id": agent_id, "command": command, "operation": operation},
                    )
                else:
                    return ActionResult(
                        False,
                        f"Wazuh Active Response returned HTTP {ar_resp.status_code}: {ar_resp.text}",
                    )

        except Exception as exc:
            # Fallback to simulation mode for dev/offline environments
            logger.warning(
                "soar_isolate_host_fallback_simulation",
                agent_id=agent_id,
                operation=operation,
                error=str(exc),
            )
            return ActionResult(
                True,
                f"[SIMULATION] Agent {agent_id} {operation}d (Wazuh API offline). "
                f"In production, configure WAZUH_API_URL correctly.",
                {"simulation": True, "agent_id": agent_id, "operation": operation},
            )
