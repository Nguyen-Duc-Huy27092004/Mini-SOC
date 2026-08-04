import pytest
import time
from app.services.ddos_engine import DDoSEngine
from app.collector.suricata_collector import SuricataCollector
from app.soar.actions.firewall_block import FirewallBlockAction

@pytest.mark.asyncio
async def test_ddos_engine_rate_tracking():
    engine = DDoSEngine(window_seconds=60, rps_threshold=5, pps_threshold=10, auto_block_enabled=True)
    ip = "198.51.100.99"

    # Record normal traffic below threshold
    for _ in range(4):
        engine.record_request(ip)

    res = await engine.evaluate_ip(ip)
    assert not res.is_ddos
    assert res.action_taken == "NONE"

    # Push above RPS threshold (HTTP Flood)
    for _ in range(3):
        engine.record_request(ip)

    res_flood = await engine.evaluate_ip(ip)
    assert res_flood.is_ddos
    assert res_flood.attack_type == "HTTP_FLOOD"
    assert res_flood.confidence_score >= 85.0
    assert res_flood.action_taken in ("AUTO_BLOCKED", "ALREADY_BLOCKED")

@pytest.mark.asyncio
async def test_manual_mitigation_action():
    engine = DDoSEngine(auto_block_enabled=True)
    target_ip = "198.51.100.88"

    # Manual block
    res_block = await engine.manual_mitigate(target_ip, operation="block", reason="Testing manual block")
    assert res_block.action_taken == "MANUAL_BLOCKED"
    assert target_ip in engine.get_blocked_ips()

    # Manual unblock
    res_unblock = await engine.manual_mitigate(target_ip, operation="unblock", reason="Testing manual unblock")
    assert res_unblock.action_taken == "MANUAL_UNBLOCKED"
    assert target_ip not in engine.get_blocked_ips()

def test_suricata_eve_parser():
    collector = SuricataCollector()
    raw_eve_json = '{"timestamp":"2026-08-04T10:00:00.000+0000","event_type":"alert","src_ip":"198.51.100.55","dest_ip":"10.0.0.5","src_port":54321,"dest_port":80,"proto":"TCP","alert":{"action":"allowed","gid":1,"signature_id":2000001,"rev":1,"signature":"SURICATA HTTP Flood Detected","category":"Attempted Denial of Service","severity":1}}'

    parsed = collector.parse_eve_line(raw_eve_json)
    assert parsed is not None
    assert parsed["event_source"] == "suricata_ids"
    assert parsed["source_ip"] == "198.51.100.55"
    assert parsed["severity"] == "CRITICAL"
    assert parsed["signature_id"] == 2000001
