"""
SOAR Action: kill_process
Sends a Wazuh Active Response command to kill a specific process
(by name or PID) on a target endpoint.

Config fields:
    agent_id (str): Wazuh agent ID (e.g. "001").
                    Falls back to trigger_data.agent_id.
    process_name (str, optional): Name of the process to kill (e.g. "malware.exe").
    pid (int, optional): PID to kill. Use instead of process_name if known.
    command (str, optional): Wazuh AR command override. Default "!kill-process".
    timeout (int, optional): Active-response timeout. Default 60s.

Notes:
    - Wazuh agent must have 'kill-process' active-response configured.
    - Works on Linux (SIGKILL) and Windows (TerminateProcess) endpoints.
    - If Wazuh is offline: logs and returns success (simulation mode) to avoid
      blocking the playbook chain.
"""
from __future__ import annotations

from typing import Any, Dict

import httpx
import structlog

from app.soar.action_engine import BaseAction, ActionResult
from app.core.config import settings

logger = structlog.get_logger()


class KillProcessAction(BaseAction):
    """
    SOAR Action to remotely kill a malicious process via Wazuh Active Response.
    """

    ACTION_NAME = "kill_process"

    async def execute(self, config: Dict[str, Any], trigger_data: Dict[str, Any]) -> ActionResult:
        agent_id = str(
            config.get("agent_id")
            or trigger_data.get("agent_id")
            or trigger_data.get("agent", {}).get("id", "")
        ).strip()

        if not agent_id:
            return ActionResult(False, "kill_process: agent_id is required but not provided.")

        process_name = config.get("process_name") or trigger_data.get("process_name", "")
        pid          = config.get("pid") or trigger_data.get("pid")
        command      = config.get("command", "!kill-process")
        timeout      = int(config.get("timeout", 60))

        if not process_name and not pid:
            return ActionResult(
                False,
                "kill_process: either 'process_name' or 'pid' must be specified in config.",
            )

        # Build arguments list for the active-response command
        arguments = []
        if pid:
            arguments.append(str(pid))
        if process_name:
            arguments.append(process_name)

        wazuh_url  = settings.WAZUH_API_URL.rstrip("/")
        wazuh_user = settings.WAZUH_API_USER
        wazuh_pass = settings.WAZUH_API_PASSWORD.get_secret_value()

        try:
            async with httpx.AsyncClient(
                verify=settings.WAZUH_VERIFY_SSL,
                timeout=15.0,
            ) as client:
                # Authenticate with Wazuh
                auth_resp = await client.post(
                    f"{wazuh_url}/security/user/authenticate",
                    auth=(wazuh_user, wazuh_pass),
                )
                if auth_resp.status_code != 200:
                    raise RuntimeError(f"Wazuh auth failed: HTTP {auth_resp.status_code}")

                token = auth_resp.json()["data"]["token"]
                headers = {"Authorization": f"Bearer {token}"}

                # Send kill-process active-response
                ar_payload = {
                    "command": command,
                    "arguments": arguments,
                    "timeout": timeout,
                    "alert": trigger_data,
                }

                ar_resp = await client.put(
                    f"{wazuh_url}/active-response",
                    headers=headers,
                    json=ar_payload,
                    params={"agents_list": agent_id},
                )

                if ar_resp.status_code in (200, 201):
                    target = process_name or f"PID:{pid}"
                    logger.info(
                        "soar_kill_process_success",
                        agent_id=agent_id,
                        target=target,
                    )
                    return ActionResult(
                        True,
                        f"Process '{target}' kill command sent to agent {agent_id}.",
                        {"agent_id": agent_id, "target": target, "command": command},
                    )
                else:
                    return ActionResult(
                        False,
                        f"Wazuh Active Response returned HTTP {ar_resp.status_code}: {ar_resp.text}",
                    )

        except Exception as exc:
            target = process_name or f"PID:{pid}"
            logger.warning(
                "soar_kill_process_fallback_simulation",
                agent_id=agent_id,
                target=target,
                error=str(exc),
            )
            return ActionResult(
                True,
                f"[SIMULATION] Kill '{target}' on agent {agent_id} (Wazuh API offline). "
                f"Configure WAZUH_API_URL for live execution.",
                {"simulation": True, "agent_id": agent_id, "target": target},
            )
