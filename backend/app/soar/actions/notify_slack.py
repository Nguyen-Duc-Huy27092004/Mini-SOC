"""
SOAR Action: notify_slack
Sends a formatted security alert notification to a Slack channel via
Incoming Webhook or Bot API.

Config fields:
    message_template (str): Message text. Supports {{variable}} placeholders
                             resolved from trigger_data.
    channel (str, optional): Override the default Slack channel.
    mention (str, optional): Slack user/group to @mention, e.g. "@soc-team".
    severity (str, optional): Used for colour-coding the attachment.
"""
from __future__ import annotations

import re
from typing import Any, Dict

import httpx
import structlog

from app.soar.action_engine import BaseAction, ActionResult
from app.core.config import settings

logger = structlog.get_logger()

# Severity → Slack attachment colour
_SEVERITY_COLOURS = {
    "critical": "#FF0000",
    "high":     "#FF6600",
    "medium":   "#FFA500",
    "low":      "#36A64F",
    "info":     "#439FE0",
}


def _resolve_template(template: str, data: dict) -> str:
    """Replace {{key}} and {{nested.key}} placeholders from trigger_data."""
    def _get(d: dict, path: str):
        val = d
        for part in path.split("."):
            if isinstance(val, dict):
                val = val.get(part, "")
            else:
                return ""
        return str(val) if val is not None else ""

    return re.sub(r"\{\{([\w.]+)\}\}", lambda m: _get(data, m.group(1)), template)


class NotifySlackAction(BaseAction):
    """
    SOAR Action that sends a rich Slack notification via Incoming Webhook.
    Silently succeeds (no error) when Slack is not configured so existing
    playbooks that include this action don't break in environments without Slack.
    """

    ACTION_NAME = "notify_slack"

    async def execute(self, config: Dict[str, Any], trigger_data: Dict[str, Any]) -> ActionResult:
        webhook_url = (
            config.get("webhook_url")
            or (settings.SLACK_WEBHOOK_URL.get_secret_value() if settings.SLACK_WEBHOOK_URL else None)
        )

        if not webhook_url:
            logger.info("notify_slack_skipped_no_webhook_configured")
            return ActionResult(
                True,
                "Slack notification skipped — SLACK_WEBHOOK_URL not configured.",
            )

        template = config.get("message_template", "🚨 SOC Alert: {{attack_type}} from {{source_ip}}")
        message  = _resolve_template(template, trigger_data)
        channel  = config.get("channel", settings.SLACK_CHANNEL)
        mention  = config.get("mention", "")
        severity = str(config.get("severity") or trigger_data.get("severity", "info")).lower()
        colour   = _SEVERITY_COLOURS.get(severity, "#439FE0")

        # Compose full text with optional mention
        full_text = f"{mention} {message}".strip() if mention else message

        # Build a rich Slack message with attachment for colour-coding
        payload = {
            "channel": channel,
            "text": full_text,
            "attachments": [
                {
                    "color": colour,
                    "fields": [
                        {"title": k.replace("_", " ").title(), "value": str(v), "short": True}
                        for k, v in trigger_data.items()
                        if not k.startswith("_") and isinstance(v, (str, int, float, bool))
                    ],
                    "footer": "Mini-SOC AI-SOAR",
                    "ts": __import__("time").time(),
                }
            ],
        }

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(webhook_url, json=payload)
                if resp.status_code == 200 and resp.text == "ok":
                    logger.info("notify_slack_sent", channel=channel, severity=severity)
                    return ActionResult(True, f"Slack notification sent to {channel}.")
                else:
                    return ActionResult(
                        False,
                        f"Slack webhook returned HTTP {resp.status_code}: {resp.text}",
                    )
        except Exception as exc:
            logger.exception("notify_slack_error")
            return ActionResult(False, f"Slack notification failed: {exc}")
