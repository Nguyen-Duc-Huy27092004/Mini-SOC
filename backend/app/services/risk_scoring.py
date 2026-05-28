"""
Risk Scoring Engine

Calculates risk scores for events, endpoints, and users.
Provides both async (DB-backed) and static (in-memory) calculation methods.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import EndpointInventory, EventRisk, WazuhEvent

logger = structlog.get_logger()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RiskScoreService:
    """
    Risk scoring engine for events, endpoints, and users.

    Scoring factors:
    - Base severity  (critical > high > medium > low)
    - Category multiplier
    - Frequency factor (many recent same-rule events = higher risk)
    - Recency factor (recent = more dangerous)
    """

    SEVERITY_SCORES: Dict[str, float] = {
        "critical": 100.0,
        "high": 75.0,
        "medium": 50.0,
        "low": 25.0,
    }

    CATEGORY_MULTIPLIERS: Dict[str, float] = {
        "authentication": 2.0,
        "malware": 3.0,
        "privilege_escalation": 2.5,
        "file_integrity_control": 1.5,
        "web_application_attack": 2.0,
        "network_attack": 1.5,
        "vulnerability": 2.0,
        "system": 1.0,
    }

    def __init__(self, db: Optional[AsyncSession] = None):
        self.db = db

    # ------------------------------------------------------------------
    # Async DB-backed methods (used by collector pipeline)
    # ------------------------------------------------------------------

    async def calculate_and_store(
        self,
        event: WazuhEvent,
        db: AsyncSession,
    ) -> Optional[EventRisk]:
        """Calculate risk score for event and persist to database."""
        try:
            base_risk = self.SEVERITY_SCORES.get(event.severity, 25.0)
            category_mult = self.CATEGORY_MULTIPLIERS.get(event.category, 1.0)
            frequency_factor = await self._calc_frequency_factor(event, db)
            recency_factor = self._calc_recency_factor(event.event_timestamp)

            event_risk = min(base_risk * category_mult * frequency_factor, 100.0)
            endpoint_risk = await self._calc_endpoint_risk(event.agent_id, db)
            user_risk = (
                await self._calc_user_risk(event.source_user, db)
                if event.source_user
                else 0.0
            )

            risk_record = EventRisk(
                event_id=event.id,
                agent_id=event.agent_id,
                source_ip=event.source_ip,
                source_user=event.source_user,
                base_risk_score=base_risk,
                severity_factor=category_mult,
                frequency_factor=frequency_factor,
                recency_factor=recency_factor,
                event_risk_score=event_risk,
                endpoint_risk_score=endpoint_risk,
                user_risk_score=user_risk,
                is_critical=event_risk > 80.0,
                is_anomalous=frequency_factor > 3.0,
            )

            db.add(risk_record)
            await db.flush()

            event.risk_score = event_risk

            await logger.ainfo(
                "risk_calculated",
                event_id=event.event_id,
                event_risk=round(event_risk, 1),
                endpoint_risk=round(endpoint_risk, 1),
            )
            return risk_record

        except Exception:
            await logger.aerror("risk_calculation_error", exc_info=True)
            return None

    async def update_endpoint_inventory_risk(
        self, agent_id: str, db: AsyncSession
    ) -> None:
        """Update cached risk scores in EndpointInventory table."""
        try:
            since = _utcnow() - timedelta(days=1)
            stmt = select(func.count(WazuhEvent.id)).where(
                and_(
                    WazuhEvent.agent_id == agent_id,
                    WazuhEvent.event_timestamp >= since,
                    WazuhEvent.severity == "critical",
                )
            )
            critical_count = (await db.execute(stmt)).scalar() or 0

            inventory = await db.scalar(
                select(EndpointInventory).where(EndpointInventory.agent_id == agent_id)
            )
            if inventory:
                inventory.critical_alert_count = critical_count
                inventory.current_risk_score = min(critical_count * 20.0, 100.0)
                await db.flush()

        except Exception:
            await logger.adebug("update_endpoint_risk_error", exc_info=True)

    # ------------------------------------------------------------------
    # Static methods — used by API providers for per-alert scoring
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_alert_risk(alert: Dict[str, Any], asset_criticality: str = "medium") -> float:
        """
        Calculate risk score for a single alert dict (no DB needed).

        Used by data providers when enriching API responses.
        """
        severity = alert.get("severity", "low")
        category = alert.get("category", "system")
        count = alert.get("count", 1)

        base = RiskScoreService.SEVERITY_SCORES.get(severity, 25.0)
        cat_mult = RiskScoreService.CATEGORY_MULTIPLIERS.get(category, 1.0)

        # Asset criticality modifier
        crit_modifiers = {"critical": 1.5, "high": 1.25, "medium": 1.0, "low": 0.75}
        crit_mult = crit_modifiers.get(asset_criticality, 1.0)

        # Frequency bonus for grouped alerts
        freq_bonus = min(1.0 + (count - 1) * 0.1, 2.0) if count > 1 else 1.0

        return round(min(base * cat_mult * crit_mult * freq_bonus, 100.0), 1)

    @staticmethod
    def calculate_asset_risk(
        alerts: List[Dict[str, Any]],
        asset_criticality: str = "medium",
    ) -> float:
        """
        Calculate aggregate risk score for an asset from its alert list.

        Used by mock/data providers for endpoint risk display.
        """
        if not alerts:
            return 0.0

        total = 0.0
        for alert in alerts:
            total += RiskScoreService.calculate_alert_risk(alert, asset_criticality)

        # Average with cap
        return round(min(total / len(alerts), 100.0), 1)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _calc_frequency_factor(self, event: WazuhEvent, db: AsyncSession) -> float:
        try:
            since = _utcnow() - timedelta(hours=1)
            stmt = select(func.count(WazuhEvent.id)).where(
                and_(
                    WazuhEvent.agent_id == event.agent_id,
                    WazuhEvent.rule_id == event.rule_id,
                    WazuhEvent.event_timestamp >= since,
                )
            )
            count = (await db.execute(stmt)).scalar() or 0
            return min(1.0 + count * 0.2, 5.0)
        except Exception:
            return 1.0

    @staticmethod
    def _calc_recency_factor(event_timestamp: datetime) -> float:
        """Recent events weight higher."""
        if event_timestamp.tzinfo is None:
            event_timestamp = event_timestamp.replace(tzinfo=timezone.utc)
        minutes_ago = (_utcnow() - event_timestamp).total_seconds() / 60
        if minutes_ago < 5:
            return 1.5
        if minutes_ago < 30:
            return 1.2
        if minutes_ago < 60:
            return 1.0
        return 0.8

    async def _calc_endpoint_risk(self, agent_id: str, db: AsyncSession) -> float:
        try:
            since = _utcnow() - timedelta(days=1)
            stmt = select(func.count(WazuhEvent.id)).where(
                and_(
                    WazuhEvent.agent_id == agent_id,
                    WazuhEvent.event_timestamp >= since,
                    WazuhEvent.severity.in_(["critical", "high"]),
                )
            )
            count = (await db.execute(stmt)).scalar() or 0
            return min(count * 5.0, 100.0)
        except Exception:
            return 0.0

    async def _calc_user_risk(self, user: str, db: AsyncSession) -> float:
        try:
            if not user:
                return 0.0
            since = _utcnow() - timedelta(days=1)
            stmt = select(func.count(WazuhEvent.id)).where(
                and_(
                    WazuhEvent.source_user == user,
                    WazuhEvent.event_timestamp >= since,
                    WazuhEvent.category.like("%authentication%"),
                    WazuhEvent.severity.in_(["critical", "high"]),
                )
            )
            count = (await db.execute(stmt)).scalar() or 0
            return min(count * 10.0, 100.0)
        except Exception:
            return 0.0
