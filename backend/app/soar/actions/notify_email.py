"""
SOAR Action: notify_email
Sends a security alert notification via Email (SMTP).

Config fields:
    subject (str, optional): Custom email subject with {{variable}} placeholders.
    severity (str, optional): Alert severity (critical, high, medium, low, info).
"""
from __future__ import annotations

import re
from typing import Any, Dict

import structlog

from app.soar.action_engine import BaseAction, ActionResult
from app.core.config import settings
from app.services.notification_service import notification_service

logger = structlog.get_logger()


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


class NotifyEmailAction(BaseAction):
    """
    SOAR Action that sends an Email notification via SMTP.
    Silently succeeds when SMTP or NOTIFICATION_ENABLED is not configured.
    """

    ACTION_NAME = "notify_email"

    async def execute(self, config: Dict[str, Any], trigger_data: Dict[str, Any]) -> ActionResult:
        if not getattr(settings, "NOTIFICATION_ENABLED", False):
            logger.info("notify_email_skipped_notifications_disabled")
            return ActionResult(
                True,
                "Email notification skipped — NOTIFICATION_ENABLED is false.",
            )

        if not getattr(settings, "SMTP_HOST", "") or not getattr(settings, "SMTP_USER", ""):
            logger.info("notify_email_skipped_no_smtp_configured")
            return ActionResult(
                True,
                "Email notification skipped — SMTP settings not fully configured.",
            )

        if not getattr(settings, "NOTIFICATION_TO_EMAILS", None):
            logger.info("notify_email_skipped_no_recipients")
            return ActionResult(
                True,
                "Email notification skipped — NOTIFICATION_TO_EMAILS is empty.",
            )

        alert_payload = dict(trigger_data)
        if config.get("severity"):
            alert_payload["severity"] = config["severity"]

        custom_subject = config.get("subject")
        if custom_subject:
            alert_payload["custom_subject"] = _resolve_template(custom_subject, alert_payload)

        try:
            results = await notification_service.send_alert(
                alert_payload,
                channels=["email"],
            )
            success = results.get("email", False)
            if success:
                logger.info("notify_email_sent_successfully")
                return ActionResult(True, "Email notification sent successfully.")
            else:
                return ActionResult(False, "Failed to send email notification (check SMTP credentials/logs).")
        except Exception as exc:
            logger.exception("notify_email_action_error")
            return ActionResult(False, f"Email notification action failed: {exc}")
