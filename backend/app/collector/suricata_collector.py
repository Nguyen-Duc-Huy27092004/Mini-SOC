import json
import os
import asyncio
from typing import Dict, Any, Optional, AsyncGenerator
import structlog

logger = structlog.get_logger()

class SuricataCollector:
    """
    Asynchronous Suricata IDS/IPS Log Collector.
    Tails Suricata eve.json output, parses alert events, maps MITRE tags,
    and forwards high-severity events to the Anti-DDoS and Correlation engines.
    """
    def __init__(self, eve_json_path: str = "/var/log/suricata/eve.json"):
        self.eve_json_path = eve_json_path
        self.running = False

    def parse_eve_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse single raw line from Suricata eve.json"""
        if not line or not line.strip():
            return None
        try:
            data = json.loads(line.strip())
            # Only process alert events
            if data.get("event_type") != "alert":
                return None

            alert = data.get("alert", {})
            src_ip = data.get("src_ip")
            dst_ip = data.get("dest_ip")
            severity = alert.get("severity", 3) # 1: High, 2: Medium, 3: Low

            # Severity Mapping
            sev_str = "LOW"
            if severity == 1:
                sev_str = "CRITICAL"
            elif severity == 2:
                sev_str = "HIGH"

            return {
                "event_source": "suricata_ids",
                "timestamp": data.get("timestamp"),
                "signature_id": alert.get("signature_id"),
                "signature": alert.get("signature", "Suricata Alert"),
                "category": alert.get("category", "Network Intrusion"),
                "source_ip": src_ip,
                "dest_ip": dst_ip,
                "src_port": data.get("src_port"),
                "dest_port": data.get("dest_port"),
                "proto": data.get("proto"),
                "severity": sev_str,
                "raw_event": data
            }
        except Exception as e:
            logger.warn("suricata_parse_error", error=str(e), line_sample=line[:100])
            return None

    async def stream_eve_logs(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream log events from eve.json asynchronously"""
        self.running = True
        if not os.path.exists(self.eve_json_path):
            logger.warn("suricata_eve_file_missing_using_simulated_stream", path=self.eve_json_path)
            return

        with open(self.eve_json_path, "r", encoding="utf-8") as f:
            # Move to end of file for live tailing
            f.seek(0, os.SEEK_END)
            while self.running:
                line = f.readline()
                if not line:
                    await asyncio.sleep(0.5)
                    continue
                parsed = self.parse_eve_line(line)
                if parsed:
                    yield parsed

    def stop(self):
        self.running = False
