import pytest
from datetime import datetime, timezone

from app.models.event import WazuhEvent
from app.services.correlation_engine import CorrelationEngine


@pytest.mark.asyncio
async def test_creates_incident_on_high_severity(db_session):
    engine = CorrelationEngine()
    event = WazuhEvent(
        event_id="e-100",
        event_timestamp=datetime.now(timezone.utc),
        agent_id="001",
        agent_name="web-1",
        manager="wazuh",
        severity="critical",
        rule_id="5710",
        rule_description="Critical auth failure",
        rule_group="authentication",
        rule_level=12,
        message="failed login",
        category="authentication",
        source_ip="203.0.113.1",
        risk_score=90.0,
        is_suppressed=False,
        wazuh_data={},
    )
    db_session.add(event)
    await db_session.flush()
    inc = await engine.process_event(event, db_session)
    assert inc is not None
    assert inc.severity == "critical"
