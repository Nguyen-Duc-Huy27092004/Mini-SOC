import pytest


@pytest.mark.asyncio
async def test_health_live(client):
    r = await client.get("/api/v1/health/live")
    assert r.status_code == 200
    assert r.json()["status"] == "alive"


@pytest.mark.asyncio
async def test_health_ready(client):
    r = await client.get("/api/v1/health/ready")
    assert r.status_code == 200
    assert "checks" in r.json()
