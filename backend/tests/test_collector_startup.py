import pytest

from app.collector.service import get_collector, start_collector


def test_get_collector_singleton():
    c1 = get_collector()
    c2 = get_collector()
    assert c1 is c2


@pytest.mark.asyncio
async def test_start_collector_no_file(monkeypatch):
    from app.core import config

    new_settings = config.settings.model_copy(update={"WAZUH_ALERTS_FILE": ""})
    monkeypatch.setattr("app.collector.service.settings", new_settings)
    task = __import__("asyncio").create_task(start_collector())
    await __import__("asyncio").sleep(0.2)
    task.cancel()
    with pytest.raises(__import__("asyncio").CancelledError):
        await task
