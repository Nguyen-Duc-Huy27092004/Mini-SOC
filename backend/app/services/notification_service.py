"""
Notification Service — Central hub for all outbound alert notifications.

Supports three channels out of the box:
  1. Slack  (Incoming Webhook)
  2. Telegram (Bot API)
  3. Email   (SMTP — reuses existing SMTP settings)

Each channel is enabled only when its credentials are configured in Settings.
The service is deliberately fire-and-forget: individual channel failures are
logged as warnings and do NOT raise exceptions, so a missing Slack token
never breaks a SOAR playbook.

Usage:
    from app.services.notification_service import notification_service

    await notification_service.send_alert(alert_data)
    await notification_service.send_approval_request(run_id, playbook_name, ...)
    await notification_service.send_incident_update(incident_id, "created", {...})
"""
from __future__ import annotations

import re
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger()

# ── Severity → visual indicators ──────────────────────────────────────────────
_SEVERITY_EMOJI = {
    "critical": "🔴",
    "high":     "🟠",
    "medium":   "🟡",
    "low":      "🟢",
    "info":     "🔵",
}
_SEVERITY_COLOUR = {
    "critical": "#FF0000",
    "high":     "#FF6600",
    "medium":   "#FFA500",
    "low":      "#36A64F",
    "info":     "#439FE0",
}


def _resolve(template: str, data: dict) -> str:
    """Replace {{key.subkey}} placeholders from a data dict."""
    def _get(d: dict, path: str) -> str:
        val = d
        for p in path.split("."):
            if isinstance(val, dict):
                val = val.get(p, "")
            else:
                return ""
        return str(val) if val is not None else ""

    return re.sub(r"\{\{([\w.]+)\}\}", lambda m: _get(data, m.group(1)), template)


class NotificationService:
    """
    Central notification hub.  Call module-level singleton `notification_service`.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def send_alert(
        self,
        alert_data: Dict[str, Any],
        channels: Optional[List[str]] = None,
    ) -> Dict[str, bool]:
        """
        Broadcast a security alert to all configured channels.

        Parameters
        ----------
        alert_data : dict
            Keys used: attack_type, source_ip, severity, confidence,
                       action_taken, agent_id, rule_id, category, etc.
        channels : list[str], optional
            Subset of ["slack", "telegram", "email"]. All enabled if None.

        Returns
        -------
        dict[str, bool]
            {channel: success} for each attempted channel.
        """
        channels = channels or ["slack", "telegram"]
        severity = str(alert_data.get("severity", "info")).lower()
        emoji    = _SEVERITY_EMOJI.get(severity, "⚠️")

        results: Dict[str, bool] = {}
        for ch in channels:
            if ch == "slack":
                results["slack"]    = await self._send_slack_alert(alert_data, emoji, severity)
            elif ch == "telegram":
                results["telegram"] = await self._send_telegram_alert(alert_data, emoji)
            elif ch == "email":
                results["email"]    = await self._send_email_alert(alert_data, emoji, severity)

        return results

    async def send_approval_request(
        self,
        run_id: UUID,
        playbook_name: str,
        action_summary: str,
        approver_role: str = "SOC Manager",
    ) -> Dict[str, bool]:
        """
        Notify approvers that a SOAR playbook is waiting for human sign-off.
        Includes a deep-link back to the Mini-SOC approval page.
        """
        approval_url = f"/soar/approvals/{run_id}"
        data = {
            "run_id": str(run_id),
            "playbook_name": playbook_name,
            "action_summary": action_summary,
            "approver_role": approver_role,
            "approval_url": approval_url,
        }

        slack_text = (
            f"⏳ *SOAR Approval Required*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• Playbook: `{playbook_name}`\n"
            f"• Actions:  {action_summary}\n"
            f"• Role:     {approver_role}\n"
            f"• <{approval_url}|🔗 Approve in Mini-SOC>"
        )
        telegram_text = (
            f"⏳ <b>SOAR Approval Required</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Playbook: <code>{playbook_name}</code>\n"
            f"Actions: {action_summary}\n"
            f"Role: {approver_role}\n"
            f"<a href='{approval_url}'>🔗 Approve in Mini-SOC</a>"
        )

        results: Dict[str, bool] = {}
        results["slack"]    = await self._post_slack(slack_text, colour="#FFA500")
        results["telegram"] = await self._post_telegram(telegram_text)
        return results

    async def send_incident_update(
        self,
        incident_id: Any,
        update_type: str,
        details: Dict[str, Any],
    ) -> Dict[str, bool]:
        """
        Notify about incident lifecycle events: created, escalated, resolved.

        Parameters
        ----------
        incident_id : Any
            UUID or int of the incident.
        update_type : str
            One of "created", "escalated", "resolved", "assigned".
        details : dict
            Incident details (severity, title, assigned_to, etc.)
        """
        type_icons = {
            "created":   "🆕",
            "escalated": "⬆️",
            "resolved":  "✅",
            "assigned":  "👤",
        }
        icon     = type_icons.get(update_type, "ℹ️")
        severity = str(details.get("severity", "info")).lower()
        colour   = _SEVERITY_COLOUR.get(severity, "#439FE0")
        title    = details.get("title", "Security Incident")

        slack_text = (
            f"{icon} *Incident {update_type.upper()}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• ID:       `{incident_id}`\n"
            f"• Title:    {title}\n"
            f"• Severity: {severity.upper()}\n"
            f"• Status:   {details.get('status', '-')}"
        )
        telegram_text = (
            f"{icon} <b>Incident {update_type.upper()}</b>\n"
            f"ID: <code>{incident_id}</code>\n"
            f"Title: {title}\n"
            f"Severity: <b>{severity.upper()}</b>"
        )

        results: Dict[str, bool] = {}
        results["slack"]    = await self._post_slack(slack_text, colour=colour)
        results["telegram"] = await self._post_telegram(telegram_text)
        return results

    # ------------------------------------------------------------------
    # Private: Slack
    # ------------------------------------------------------------------

    async def _send_slack_alert(
        self,
        data: Dict[str, Any],
        emoji: str,
        severity: str,
    ) -> bool:
        attack_type  = data.get("attack_type", "UNKNOWN")
        source_ip    = data.get("source_ip", "N/A")
        confidence   = data.get("confidence", data.get("attack_confidence", 0))
        action_taken = data.get("action_taken", "LOG_ONLY")
        colour       = _SEVERITY_COLOUR.get(severity, "#439FE0")

        text = (
            f"{emoji} *[{severity.upper()}]* DDoS/Threat Detected\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• Attack: `{attack_type}`\n"
            f"• Source IP: `{source_ip}`\n"
            f"• Confidence: *{confidence}%*\n"
            f"• Action: *{action_taken}*"
        )
        return await self._post_slack(text, colour=colour, data=data)

    async def _post_slack(
        self,
        text: str,
        colour: str = "#439FE0",
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        webhook_url = (
            settings.SLACK_WEBHOOK_URL.get_secret_value()
            if settings.SLACK_WEBHOOK_URL
            else None
        )
        if not webhook_url:
            return True  # Silently skip if not configured

        fields = []
        if data:
            fields = [
                {"title": k.replace("_", " ").title(), "value": str(v), "short": True}
                for k, v in data.items()
                if not k.startswith("_") and isinstance(v, (str, int, float, bool))
            ]

        payload: Dict[str, Any] = {
            "text": text,
            "attachments": [{"color": colour, "fields": fields, "ts": time.time()}],
        }
        if settings.SLACK_CHANNEL:
            payload["channel"] = settings.SLACK_CHANNEL

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(webhook_url, json=payload)
                ok   = resp.status_code == 200 and resp.text == "ok"
                if not ok:
                    logger.warning("notification_slack_failed", status=resp.status_code, body=resp.text)
                return ok
        except Exception as exc:
            logger.warning("notification_slack_error", error=str(exc))
            return False

    # ------------------------------------------------------------------
    # Private: Telegram
    # ------------------------------------------------------------------

    async def _send_telegram_alert(self, data: Dict[str, Any], emoji: str) -> bool:
        attack_type  = data.get("attack_type", "UNKNOWN")
        source_ip    = data.get("source_ip", "N/A")
        confidence   = data.get("confidence", data.get("attack_confidence", 0))
        action_taken = data.get("action_taken", "LOG_ONLY")
        severity     = str(data.get("severity", "info")).upper()

        text = (
            f"{emoji} <b>[Mini-SOC Alert — {severity}]</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔴 Attack: <code>{attack_type}</code>\n"
            f"📡 Source IP: <code>{source_ip}</code>\n"
            f"📊 Confidence: <b>{confidence}%</b>\n"
            f"⚡ Action: <b>{action_taken}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>Mini-SOC AI-SOAR</i>"
        )
        return await self._post_telegram(text)

    async def _post_telegram(self, text: str) -> bool:
        bot_token = (
            settings.TELEGRAM_BOT_TOKEN.get_secret_value()
            if settings.TELEGRAM_BOT_TOKEN
            else None
        )
        chat_id = settings.TELEGRAM_CHAT_ID

        if not bot_token or not chat_id:
            return True  # Silently skip if not configured

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                ok   = resp.json().get("ok", False)
                if not ok:
                    logger.warning("notification_telegram_failed", response=resp.text)
                return ok
        except Exception as exc:
            logger.warning("notification_telegram_error", error=str(exc))
            return False

    # ------------------------------------------------------------------
    # Private: Email
    # ------------------------------------------------------------------

    async def _send_email_alert(
        self,
        data: Dict[str, Any],
        emoji: str,
        severity: str,
    ) -> bool:
        if not settings.NOTIFICATION_ENABLED or not settings.NOTIFICATION_TO_EMAILS:
            return True

        attack_type = data.get("attack_type", "UNKNOWN")
        source_ip   = data.get("source_ip", "N/A")

        subject = f"{emoji} [Mini-SOC] {severity.upper()} — {attack_type} from {source_ip}"
        body    = (
            f"<h2>{emoji} Security Alert — {severity.upper()}</h2>"
            f"<table border='1' cellpadding='6'>"
            + "".join(
                f"<tr><td><b>{k.replace('_',' ').title()}</b></td><td>{v}</td></tr>"
                for k, v in data.items()
                if not k.startswith("_")
            )
            + "</table><br><i>Sent by Mini-SOC AI-SOAR</i>"
        )

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = settings.SMTP_FROM or settings.SMTP_USER
            msg["To"]      = ", ".join(settings.NOTIFICATION_TO_EMAILS)
            msg.attach(MIMEText(body, "html"))

            smtp_pass = settings.SMTP_PASSWORD.get_secret_value() if settings.SMTP_PASSWORD else ""
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
                server.ehlo()
                server.starttls()
                if settings.SMTP_USER and smtp_pass:
                    server.login(settings.SMTP_USER, smtp_pass)
                server.sendmail(
                    msg["From"],
                    settings.NOTIFICATION_TO_EMAILS,
                    msg.as_string(),
                )
            logger.info("notification_email_sent", to=settings.NOTIFICATION_TO_EMAILS)
            return True
        except Exception as exc:
            logger.warning("notification_email_error", error=str(exc))
            return False


# ── Module-level singleton ─────────────────────────────────────────────────────
notification_service = NotificationService()
