"""
Enterprise Event Normalizer & Router
Production-grade event normalization pipeline for Mini SOC Portal.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

import structlog
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.collector.alerts_tail import AlertParser
from app.models.event import WazuhEvent

logger = structlog.get_logger()

# =============================================================================
# METRICS
# =============================================================================

class RouterMetrics:
    normalized_events = 0
    failed_normalizations = 0
    suppressed_events = 0
    published_events = 0
    db_failures = 0
    publish_failures = 0
    geoip_failures = 0


# =============================================================================
# NORMALIZER
# =============================================================================

class EventNormalizer:

    def __init__(
        self,
        geoip_service=None,
        max_message_size: int = 8192,
    ):

        self.geoip_service = geoip_service
        self.parser = AlertParser()
        self.max_message_size = max_message_size

    async def normalize(
        self,
        raw_alert: dict,
    ) -> Optional[WazuhEvent]:

        started = time.time()

        try:

            parsed = self.parser.parse(raw_alert)

            if not parsed:
                RouterMetrics.failed_normalizations += 1
                return None

            source_geo = await self._safe_geoip_lookup(
                parsed.source_ip
            )

            dest_geo = await self._safe_geoip_lookup(
                parsed.destination_ip
            )

            manager_name = (
                raw_alert.get("manager", {}).get("name")
                if isinstance(raw_alert.get("manager"), dict)
                else str(raw_alert.get("manager", "wazuh-manager"))
            )
            rule_groups = raw_alert.get("rule", {}).get("groups", [])
            rule_group = rule_groups[0] if rule_groups else parsed.category

            event = WazuhEvent(
                id=uuid.uuid4(),
                event_id=parsed.event_id or self._generate_correlation_id(parsed),
                event_timestamp=parsed.timestamp,
                agent_id=parsed.agent_id,
                agent_name=parsed.agent_name,
                manager=manager_name,
                source_ip=parsed.source_ip,
                source_port=parsed.source_port,
                source_user=parsed.source_user,
                dest_ip=parsed.destination_ip,
                dest_port=parsed.destination_port,
                dest_user=parsed.destination_user,
                severity=parsed.severity,
                rule_id=parsed.rule_id,
                rule_description=parsed.rule_description,
                rule_group=rule_group,
                rule_level=parsed.rule_level,
                message=self._sanitize_message(parsed.message),
                category=parsed.category,
                source_country=source_geo.get("country"),
                source_city=source_geo.get("city"),
                dest_country=dest_geo.get("country"),
                risk_score=self._calculate_risk_score(parsed, source_geo),
                is_suppressed=False,
                wazuh_data=self._truncate_raw(raw_alert),
            )

            RouterMetrics.normalized_events += 1

            logger.debug(
                "event_normalized",
                event_id=event.event_id,
                duration_ms=int(
                    (time.time() - started) * 1000
                )
            )

            return event

        except ValidationError:

            RouterMetrics.failed_normalizations += 1

            logger.exception(
                "event_validation_failed"
            )

            return None

        except Exception:

            RouterMetrics.failed_normalizations += 1

            logger.exception(
                "event_normalization_failed"
            )

            return None

    async def _safe_geoip_lookup(
        self,
        ip: Optional[str]
    ) -> dict:

        if not ip or not self.geoip_service:
            return {}

        try:

            result = await self.geoip_service.lookup(ip)

            return result or {}

        except Exception:

            RouterMetrics.geoip_failures += 1

            logger.exception(
                "geoip_lookup_failed",
                ip=ip
            )

            return {}

    def _sanitize_message(
        self,
        message: str
    ) -> str:

        if not message:
            return ""

        message = message.replace("\x00", "")

        if len(message) > self.max_message_size:
            message = message[:self.max_message_size]

        return message.strip()

    def _truncate_raw(
        self,
        raw: dict
    ) -> dict:

        """
        Prevent oversized payload storage.
        """

        sanitized = dict(raw)

        if "full_log" in sanitized:

            full_log = str(
                sanitized["full_log"]
            )

            if len(full_log) > 4096:
                sanitized["full_log"] = (
                    full_log[:4096]
                )

        return sanitized

    def _generate_correlation_id(
        self,
        parsed,
    ) -> str:

        seed = (
            f"{parsed.rule_id}:"
            f"{parsed.source_ip}:"
            f"{parsed.agent_id}:"
            f"{parsed.timestamp.minute}"
        )

        return hashlib.sha256(
            seed.encode()
        ).hexdigest()

    def _calculate_risk_score(
        self,
        parsed,
        geo: dict,
    ) -> float:

        score = 0.0

        severity_scores = {
            "critical": 90,
            "high": 70,
            "medium": 45,
            "low": 20,
        }

        score += severity_scores.get(
            parsed.severity,
            0
        )

        if parsed.source_ip:
            score += 5

        if parsed.source_user:
            score += 5

        if geo.get("country") not in [None, "VN"]:
            score += 10

        if parsed.rule_level >= 12:
            score += 10

        return min(score, 100.0)


# =============================================================================
# EVENT ROUTER
# =============================================================================

class EventRouter:

    def __init__(
        self,
        suppression_service=None,
        risk_service=None,
        publisher=None,
    ):

        self.suppression_service = suppression_service
        self.risk_service = risk_service
        self.publisher = publisher

    async def route_event(
        self,
        event: WazuhEvent,
        db: AsyncSession,
    ) -> bool:

        started = time.time()

        try:

            async with self._transaction(db):

                # ============================================================
                # PERSIST INITIAL EVENT (Ensure event_id exists for relations)
                # ============================================================
                db.add(event)
                await db.flush()

                # ============================================================
                # SUPPRESSION
                # ============================================================

                if self.suppression_service:

                    suppressed = (
                        await self.suppression_service
                        .check_and_update(event, db)
                    )

                    if suppressed:

                        event.is_suppressed = True

                        db.add(event)

                        RouterMetrics.suppressed_events += 1

                        logger.info(
                            "event_suppressed",
                            event_id=event.event_id
                        )

                        return False

                # ============================================================
                # RISK SCORING
                # ============================================================

                if self.risk_service:
                    risk_row = await self.risk_service.calculate_and_store(event, db)
                    if risk_row:
                        event.risk_score = risk_row.event_risk_score

                # ============================================================
                # CORRELATION
                # ============================================================

                from app.services.correlation_engine import correlation_engine

                await correlation_engine.process_event(event, db)

                # ============================================================
                # DIRECT CRITICAL ALERT EMAIL
                # Gửi mail cho mọi Wazuh critical event bất kể correlation.
                # Cooldown 30 phút theo event_id để tránh spam.
                # ============================================================
                if event.severity == "critical" or (
                    event.rule_level and event.rule_level >= 13
                ):
                    asyncio.ensure_future(
                        _send_wazuh_critical_email(event)
                    )

            # ================================================================
            # PUBLISH OUTSIDE TRANSACTION
            # ================================================================

            if self.publisher:

                try:

                    await self.publisher.publish_event(
                        event
                    )

                    RouterMetrics.published_events += 1

                except Exception:

                    RouterMetrics.publish_failures += 1

                    logger.exception(
                        "event_publish_failed",
                        event_id=event.event_id
                    )

            logger.info(
                "event_processed",
                event_id=event.event_id,
                severity=event.severity,
                duration_ms=int(
                    (time.time() - started) * 1000
                )
            )

            return True

        except SQLAlchemyError:

            RouterMetrics.db_failures += 1

            logger.exception(
                "database_transaction_failed",
                event_id=event.event_id
            )

            return False

        except Exception:

            logger.exception(
                "event_router_failed",
                event_id=event.event_id
            )

            return False

    # =========================================================================
    # TRANSACTION MANAGER
    # =========================================================================

    @asynccontextmanager
    async def _transaction(
        self,
        db: AsyncSession,
    ):

        try:

            yield

            await db.commit()

        except Exception:

            await db.rollback()

            raise


# =============================================================================
# WAZUH CRITICAL DIRECT EMAIL
# =============================================================================

# In-memory cooldown: key = event_id hoặc rule_id+agent_id, ttl = 1800s
_critical_email_cooldowns: dict[str, float] = {}


async def _send_wazuh_critical_email(event) -> None:
    """
    Gửi email ngay cho mọi Wazuh event severity=critical (hoặc rule_level>=13).
    Không phụ thuộc vào correlation engine có tạo Incident hay không.
    Cooldown 1800s (30 phút) theo rule_id+agent_id để tránh spam.
    """
    try:
        from app.core.config import settings
        if not getattr(settings, "NOTIFICATION_ENABLED", False):
            return
        if not getattr(settings, "NOTIFICATION_TO_EMAILS", None):
            return

        # Cooldown key: rule + agent (gộp các event giống nhau liên tiếp)
        cd_key = f"{event.rule_id}:{event.agent_id}"
        now = time.monotonic()
        last = _critical_email_cooldowns.get(cd_key, 0)
        if now - last < 1800:
            return
        _critical_email_cooldowns[cd_key] = now

        # Cleanup expired entries to prevent memory leak (keep dict bounded)
        expired_keys = [k for k, v in _critical_email_cooldowns.items() if now - v > 3600]
        for k in expired_keys:
            del _critical_email_cooldowns[k]

        from app.services.notification_service import notification_service
        alert_data = {
            "event_type": "WAZUH CRITICAL ALERT",
            "severity": (event.severity or "critical").upper(),
            "rule_id": event.rule_id or "N/A",
            "rule_level": str(event.rule_level or "N/A"),
            "description": event.rule_description or "",
            "agent_id": event.agent_id or "N/A",
            "agent_name": event.agent_name or "N/A",
            "source_ip": event.source_ip or "N/A",
            "category": event.category or "N/A",
            "timestamp": (
                event.event_timestamp.isoformat()
                if event.event_timestamp
                else datetime.now(timezone.utc).isoformat()
            ),
            "custom_subject": (
                f"\U0001f534 [Mini-SOC] WAZUH CRITICAL \u2014 "
                f"{event.rule_description[:60] if event.rule_description else 'Alert'}"
                f" | Agent: {event.agent_name or event.agent_id or 'N/A'}"
            ),
        }
        await notification_service._send_email_alert(alert_data, "\U0001f534", "critical")
        logger.info(
            "wazuh_critical_email_sent",
            rule_id=event.rule_id,
            agent=event.agent_id,
            severity=event.severity,
        )
    except Exception:
        logger.warning("wazuh_critical_email_failed", exc_info=True)