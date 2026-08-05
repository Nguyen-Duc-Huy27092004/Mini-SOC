"""
SOAR Action: escalate_incident
Creates a new security incident or escalates an existing one in the
Mini-SOC PostgreSQL database.

Config fields:
    new_severity (str): Severity for the incident. One of:
                        "critical", "high", "medium", "low".
                        Default: inferred from trigger_data.severity.
    title_template (str, optional): Incident title. Supports {{placeholders}}.
    description_template (str, optional): Incident description. Supports {{placeholders}}.
    add_note (str, optional): Additional analyst note appended to description.
    assign_to_role (str, optional): Not yet wired to a specific user — for future use.
    correlation_type (str, optional): Override correlation type label.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

import structlog

from app.soar.action_engine import BaseAction, ActionResult

logger = structlog.get_logger()

_DEFAULT_TITLE = "SOAR Auto-Incident: {{attack_type}} from {{source_ip}}"
_DEFAULT_DESC  = (
    "Incident automatically created by SOAR playbook.\n\n"
    "Attack Type: {{attack_type}}\n"
    "Source IP:   {{source_ip}}\n"
    "Confidence:  {{confidence}}%\n"
    "Trigger:     {{trigger_source}}\n"
)

_SEVERITY_MAP = {"critical": "critical", "high": "high", "medium": "medium", "low": "low"}


def _resolve(template: str, data: dict) -> str:
    def _get(d: dict, path: str) -> str:
        val = d
        for p in path.split("."):
            if isinstance(val, dict):
                val = val.get(p, "")
            else:
                return ""
        return str(val) if val is not None else ""

    return re.sub(r"\{\{([\w.]+)\}\}", lambda m: _get(data, m.group(1)), template)


class EscalateIncidentAction(BaseAction):
    """
    SOAR Action that creates/escalates a security incident in the DB.
    Uses async SQLAlchemy session factory so it can run inside the SOAR
    worker without needing an injected session.
    """

    ACTION_NAME = "escalate_incident"

    async def execute(self, config: Dict[str, Any], trigger_data: Dict[str, Any]) -> ActionResult:
        from app.core.database import async_session_maker
        from app.models.incident import Incident
        from sqlalchemy import select

        # Resolve severity
        raw_sev = (
            config.get("new_severity")
            or trigger_data.get("severity", "medium")
        ).lower()
        severity = _SEVERITY_MAP.get(raw_sev, "medium")

        # Resolve title and description
        title = _resolve(
            config.get("title_template", _DEFAULT_TITLE), trigger_data
        )
        description = _resolve(
            config.get("description_template", _DEFAULT_DESC), trigger_data
        )
        if config.get("add_note"):
            description += f"\n\n📝 Analyst Note:\n{config['add_note']}"

        # Build correlation key: prefer source_ip, fallback to attack_type
        source_ip    = str(trigger_data.get("source_ip", "unknown"))
        attack_type  = str(trigger_data.get("attack_type", "UNKNOWN"))
        correlation_key = f"soar:{attack_type.lower()}:{source_ip}"
        correlation_type = config.get("correlation_type", "soar_auto")

        try:
            async with async_session_maker() as db:
                # Check if an open incident with the same key already exists
                stmt = select(Incident).where(
                    Incident.correlation_key == correlation_key,
                    Incident.status.in_(["open", "investigating"]),
                )
                existing = (await db.execute(stmt)).scalars().first()

                if existing:
                    # Escalate: bump alert count and potentially severity
                    existing.alert_count += 1
                    severity_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
                    if severity_rank.get(severity, 0) > severity_rank.get(existing.severity, 0):
                        existing.severity = severity
                        existing.description += f"\n\n⬆️ [SOAR Escalated to {severity.upper()}] {datetime.now(timezone.utc).isoformat()}"
                    await db.commit()
                    logger.info(
                        "soar_incident_escalated",
                        incident_id=str(existing.id),
                        new_severity=severity,
                        alert_count=existing.alert_count,
                    )
                    return ActionResult(
                        True,
                        f"Incident {existing.id} escalated (alert_count={existing.alert_count}, severity={severity}).",
                        {"incident_id": str(existing.id), "action": "escalated"},
                    )
                else:
                    # Create new incident
                    incident = Incident(
                        title=title,
                        description=description,
                        status="open",
                        severity=severity,
                        correlation_key=correlation_key,
                        correlation_type=correlation_type,
                        source_ip=source_ip if source_ip != "unknown" else None,
                        category=trigger_data.get("category"),
                        mitre_tactic=trigger_data.get("mitre_tactic"),
                        mitre_technique=trigger_data.get("mitre_technique"),
                        risk_score=float(trigger_data.get("confidence", 0.0)),
                        alert_count=1,
                    )
                    db.add(incident)
                    await db.commit()
                    await db.refresh(incident)
                    logger.info(
                        "soar_incident_created",
                        incident_id=str(incident.id),
                        severity=severity,
                        source_ip=source_ip,
                    )
                    return ActionResult(
                        True,
                        f"Incident created: {incident.id} (severity={severity}).",
                        {"incident_id": str(incident.id), "action": "created"},
                    )

        except Exception as exc:
            logger.exception("soar_escalate_incident_error")
            return ActionResult(False, f"Failed to create/escalate incident: {exc}")
