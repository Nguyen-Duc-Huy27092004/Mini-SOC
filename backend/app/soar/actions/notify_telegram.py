"""
SOAR Action: notify_telegram
Sends a security alert notification to a Telegram chat/group/channel
via the Telegram Bot API (sendMessage).

Config fields:
    message_template (str): Message text. Supports {{variable}} placeholders
                             resolved from trigger_data. HTML formatting allowed.
    chat_id (str, optional): Override the default TELEGRAM_CHAT_ID from settings.
    parse_mode (str): "HTML" (default) or "Markdown".
    disable_notification (bool): Send silently. Default False.
"""
from __future__ import annotations

import re
from typing import Any, Dict

import httpx
import structlog

from app.soar.action_engine import BaseAction, ActionResult
from app.core.config import settings

logger = structlog.get_logger()

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

_DEFAULT_TEMPLATE = (
    "🚨 <b>[Mini-SOC Alert]</b>\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "🔴 Attack: <code>{{attack_type}}</code>\n"
    "📡 Source IP: <code>{{source_ip}}</code>\n"
    "📊 Confidence: <b>{{confidence}}%</b>\n"
    "⚡ Action: <b>{{action_taken}}</b>\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "<i>Mini-SOC AI-SOAR Auto-Notification</i>"
)


def _resolve_template(template: str, data: dict) -> str:
    """Replace {{key}} placeholders from trigger_data."""
    def _get(d: dict, path: str):
        val = d
        for part in path.split("."):
            if isinstance(val, dict):
                val = val.get(part, "")
            else:
                return ""
        return str(val) if val is not None else ""

    return re.sub(r"\{\{([\w.]+)\}\}", lambda m: _get(data, m.group(1)), template)


class NotifyTelegramAction(BaseAction):
    """
    SOAR Action that sends a Telegram message via Bot API.
    Silently succeeds when Telegram is not configured.
    """

    ACTION_NAME = "notify_telegram"

    async def execute(self, config: Dict[str, Any], trigger_data: Dict[str, Any]) -> ActionResult:
        # Resolve bot token
        bot_token = (
            config.get("bot_token")
            or (settings.TELEGRAM_BOT_TOKEN.get_secret_value() if settings.TELEGRAM_BOT_TOKEN else None)
        )
        if not bot_token:
            logger.info("notify_telegram_skipped_no_token")
            return ActionResult(
                True,
                "Telegram notification skipped — TELEGRAM_BOT_TOKEN not configured.",
            )

        # Resolve chat ID
        chat_id = str(
            config.get("chat_id")
            or settings.TELEGRAM_CHAT_ID
            or ""
        ).strip()
        if not chat_id:
            return ActionResult(False, "Telegram chat_id not configured.")

        template   = config.get("message_template", _DEFAULT_TEMPLATE)
        text       = _resolve_template(template, trigger_data)
        parse_mode = config.get("parse_mode", "HTML")
        silent     = config.get("disable_notification", False)

        url = _TELEGRAM_API.format(token=bot_token)
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_notification": silent,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                data = resp.json()
                if data.get("ok"):
                    logger.info("notify_telegram_sent", chat_id=chat_id)
                    return ActionResult(True, f"Telegram notification sent to chat {chat_id}.")
                else:
                    err = data.get("description", "Unknown error")
                    return ActionResult(False, f"Telegram API error: {err}")
        except Exception as exc:
            logger.exception("notify_telegram_error")
            return ActionResult(False, f"Telegram notification failed: {exc}")
