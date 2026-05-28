import pytest
from datetime import datetime, timezone
from uuid import uuid4

from app.models.event import WazuhEvent
from app.services.wazuh_data_service import WazuhDataService


@pytest.mark.asyncio
async def test_summary_empty_db(db_session):
    svc = WazuhDataService()
    summary = await svc.get_summary(db_session)
    assert summary.alerts_today == 0
    assert summary.agents_total >= 0


@pytest.mark.asyncio
async def test_alerts_pagination(db_session):
    evt = WazuhEvent(
        event_id="evt-1",
        event_timestamp=datetime.now(timezone.utc),
        agent_id="001",
        agent_name="srv-1",
        manager="wazuh",
        severity="high",
        rule_id="5710",
        rule_description="SSH brute force",
        rule_group="authentication",
        rule_level=10,
        message="test",
        category="authentication",
        risk_score=70.0,
        is_suppressed=False,
        wazuh_data={},
    )
    db_session.add(evt)
    await db_session.commit()

    svc = WazuhDataService()
    result = await svc.get_alerts(db_session, page=1, page_size=10, severity="high")
    assert result.total >= 1
    assert result.alerts[0].severity == "high"
