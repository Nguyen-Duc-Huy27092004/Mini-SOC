"""
Alert Suppression & Deduplication Engine

Prevents alert spam through:
- Exact deduplication (same alert fingerprint within window)
- Burst grouping  (many alerts in short time)
- Repeated attack grouping (same attacker, same rule, sustained)
- Thresholding

Also provides suppress_and_group() for in-memory grouping (used by API layer).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import md5
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import AlertSuppression, WazuhEvent

logger = structlog.get_logger()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AlertSuppressionService:
    """Alert suppression and grouping engine."""

    def __init__(
        self,
        dedup_window_minutes: int = 5,
        burst_threshold: int = 10,
        burst_window_minutes: int = 5,
        repeat_threshold: int = 20,
    ):
        self.dedup_window = timedelta(minutes=dedup_window_minutes)
        self.burst_threshold = burst_threshold
        self.burst_window = timedelta(minutes=burst_window_minutes)
        self.repeat_threshold = repeat_threshold
        self.repeat_window = timedelta(hours=1)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def check_and_update(
        self,
        event: WazuhEvent,
        db: AsyncSession,
    ) -> bool:
        """
        Check if event should be suppressed.

        Returns:
            True  → event is a duplicate/burst/repeated — suppress it
            False → event should be published
        """
        try:
            if await self._is_duplicate(event, db):
                await logger.ainfo("alert_suppressed_duplicate", event_id=event.event_id)
                return True

            if await self._is_burst(event, db):
                await logger.ainfo("alert_suppressed_burst", event_id=event.event_id)
                return True

            if await self._is_repeated_attack(event, db):
                await logger.ainfo("alert_suppressed_repeated", event_id=event.event_id)
                return True

            return False

        except Exception:
            await logger.aerror("suppression_check_error", exc_info=True)
            return False  # On error, allow through

    async def expire_old_suppressions(self, db: AsyncSession) -> int:
        """Expire stale suppression records (maintenance)."""
        try:
            stmt = select(AlertSuppression).where(
                AlertSuppression.suppression_expires_at < _utcnow(),
                AlertSuppression.status == "active",
            )
            result = await db.execute(stmt)
            rows = result.scalars().all()
            count = 0
            for sup in rows:
                sup.status = "expired"
                count += 1
                if count % 200 == 0:
                    await db.flush()
            await db.commit()
            await logger.ainfo("suppressions_expired", count=count)
            return count
        except Exception:
            await logger.aerror("expire_suppressions_error", exc_info=True)
            return 0

    async def acknowledge_suppression(
        self,
        suppression_id: str,
        user_id: str,
        db: AsyncSession,
    ) -> bool:
        """Mark suppression as acknowledged by user."""
        try:
            import uuid
            stmt = select(AlertSuppression).where(
                AlertSuppression.id == uuid.UUID(suppression_id)
            )
            sup = await db.scalar(stmt)
            if sup:
                sup.status = "acknowledged"
                sup.acknowledged_at = _utcnow()
                sup.acknowledged_by_id = uuid.UUID(user_id)
                await db.commit()
                return True
            return False
        except Exception:
            await logger.aerror("acknowledge_suppression_error", exc_info=True)
            return False

    # ------------------------------------------------------------------
    # Static helper — used by API data providers for in-memory grouping
    # ------------------------------------------------------------------

    @staticmethod
    def suppress_and_group(
        alerts: List[Dict[str, Any]],
        window_minutes: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        In-memory deduplication and grouping for API-level suppression.

        Groups alerts with same (rule_id, agent_id, severity) within time window.
        Used by the data providers to present grouped results to the UI.

        Args:
            alerts: List of alert dicts (already sorted newest-first)
            window_minutes: Grouping window in minutes

        Returns:
            Deduplicated/grouped list with 'count' field added
        """
        if not alerts:
            return []

        window = timedelta(minutes=window_minutes)
        grouped: Dict[str, Dict[str, Any]] = {}
        result: List[Dict[str, Any]] = []

        for alert in alerts:
            # Build group key
            rule_id = alert.get("rule_id") or alert.get("rule", {}).get("id", "")
            agent_id = alert.get("agent_id", "")
            severity = alert.get("severity", "low")
            src_ip = alert.get("src_ip", "")
            key = f"{rule_id}:{agent_id}:{severity}:{src_ip}"

            # Parse timestamp
            ts_raw = alert.get("timestamp", "")
            try:
                ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00")) if ts_raw else _utcnow()
            except ValueError:
                ts = _utcnow()

            if key in grouped:
                existing = grouped[key]
                existing_ts_raw = existing.get("timestamp", "")
                try:
                    existing_ts = datetime.fromisoformat(
                        existing_ts_raw.replace("Z", "+00:00")
                    )
                except ValueError:
                    existing_ts = _utcnow()

                # Same alert within window → group
                if abs((ts - existing_ts).total_seconds()) <= window.total_seconds():
                    existing["count"] = existing.get("count", 1) + 1
                    continue

            # New group
            alert_copy = dict(alert)
            alert_copy["count"] = alert_copy.get("count", 1)
            grouped[key] = alert_copy
            result.append(alert_copy)

        return result

    # ------------------------------------------------------------------
    # Internal checks
    # ------------------------------------------------------------------

    async def _is_duplicate(self, event: WazuhEvent, db: AsyncSession) -> bool:
        """Exact-fingerprint dedup within dedup_window."""
        try:
            dedup_key = self._fingerprint(event)
            now = _utcnow()

            stmt = select(AlertSuppression).where(
                and_(
                    AlertSuppression.group_key == dedup_key,
                    AlertSuppression.suppression_type == "deduplication",
                    AlertSuppression.suppression_expires_at > now,
                    AlertSuppression.status == "active",
                )
            )
            existing = await db.scalar(stmt)
            if existing:
                existing.alert_count += 1
                existing.updated_at = now
                await db.flush()
                return True

            # Create new dedup window
            sup = AlertSuppression(
                event_id=event.id,
                suppression_type="deduplication",
                group_key=dedup_key,
                agent_id=event.agent_id,
                rule_id=event.rule_id,
                source_ip=event.source_ip,
                dest_ip=event.dest_ip,
                suppression_expires_at=now + self.dedup_window,
                alert_count=1,
                display_alert_count=1,
            )
            db.add(sup)
            await db.flush()
            return False

        except Exception:
            await logger.adebug("duplicate_check_error", exc_info=True)
            return False

    async def _is_burst(self, event: WazuhEvent, db: AsyncSession) -> bool:
        """Detect alert bursts (many similar alerts in short window)."""
        try:
            cutoff = _utcnow() - self.burst_window

            stmt = select(func.count(WazuhEvent.id)).where(
                and_(
                    WazuhEvent.agent_id == event.agent_id,
                    WazuhEvent.rule_id == event.rule_id,
                    WazuhEvent.event_timestamp >= cutoff,
                )
            )
            result = await db.execute(stmt)
            count = result.scalar() or 0

            if count < self.burst_threshold:
                return False

            # Create/update burst suppression group
            now = _utcnow()
            burst_key = f"burst:{event.agent_id}:{event.rule_id}:{int(cutoff.timestamp())}"
            stmt2 = select(AlertSuppression).where(
                and_(
                    AlertSuppression.group_key == burst_key,
                    AlertSuppression.suppression_type == "burst_grouping",
                    AlertSuppression.status == "active",
                )
            )
            existing = await db.scalar(stmt2)
            if existing:
                existing.alert_count = count
                existing.updated_at = now
            else:
                db.add(AlertSuppression(
                    event_id=event.id,
                    suppression_type="burst_grouping",
                    group_key=burst_key,
                    agent_id=event.agent_id,
                    rule_id=event.rule_id,
                    suppression_expires_at=now + self.burst_window,
                    alert_count=count,
                    display_alert_count=1,
                ))
            await db.flush()
            return True

        except Exception:
            await logger.adebug("burst_check_error", exc_info=True)
            return False

    async def _is_repeated_attack(self, event: WazuhEvent, db: AsyncSession) -> bool:
        """Detect sustained repeated attacks from same source IP."""
        try:
            if not event.source_ip:
                return False

            cutoff = _utcnow() - self.repeat_window
            stmt = select(func.count(WazuhEvent.id)).where(
                and_(
                    WazuhEvent.agent_id == event.agent_id,
                    WazuhEvent.rule_id == event.rule_id,
                    WazuhEvent.source_ip == event.source_ip,
                    WazuhEvent.event_timestamp >= cutoff,
                )
            )
            result = await db.execute(stmt)
            count = result.scalar() or 0

            if count < self.repeat_threshold:
                return False

            now = _utcnow()
            group_key = (
                f"repeat:{event.agent_id}:{event.rule_id}:{event.source_ip}"
            )
            stmt2 = select(AlertSuppression).where(
                and_(
                    AlertSuppression.group_key == group_key,
                    AlertSuppression.suppression_type == "repeated_attack",
                    AlertSuppression.status == "active",
                )
            )
            existing = await db.scalar(stmt2)
            if existing:
                existing.alert_count = count
                existing.updated_at = now
            else:
                db.add(AlertSuppression(
                    event_id=event.id,
                    suppression_type="repeated_attack",
                    group_key=group_key,
                    agent_id=event.agent_id,
                    rule_id=event.rule_id,
                    source_ip=event.source_ip,
                    suppression_expires_at=now + self.repeat_window,
                    alert_count=count,
                    display_alert_count=5,
                ))
            await db.flush()
            return True

        except Exception:
            await logger.adebug("repeated_attack_check_error", exc_info=True)
            return False

    @staticmethod
    def _fingerprint(event: WazuhEvent) -> str:
        """Generate dedup fingerprint for an event."""
        raw = f"{event.agent_id}:{event.rule_id}:{event.source_ip}:{event.dest_ip}:{event.source_user}"
        return md5(raw.encode()).hexdigest()  # noqa: S324 — not crypto use
