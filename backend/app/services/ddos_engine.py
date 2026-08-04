from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple
import structlog

from app.soar.action_engine import ActionEngine

logger = structlog.get_logger()

class DDoSMitigationResult:
    def __init__(
        self,
        is_ddos: bool,
        attack_type: str,
        confidence_score: float,
        target_ip: str,
        action_taken: str,
        message: str
    ):
        self.is_ddos = is_ddos
        self.attack_type = attack_type
        self.confidence_score = confidence_score
        self.target_ip = target_ip
        self.action_taken = action_taken
        self.message = message

class DDoSEngine:
    """
    Real-Time Anti-DDoS & Rate Monitoring Engine.
    Tracks requests/packets per sliding window and automatically triggers
    SOAR Firewall IP Block when DDoS threshold (Confidence >= 85%) is exceeded.
    """
    def __init__(
        self,
        window_seconds: int = 60,
        rps_threshold: int = 100, # HTTP Flood threshold
        pps_threshold: int = 500, # SYN/UDP/ICMP Flood threshold
        auto_block_enabled: bool = True
    ):
        self.window_seconds = window_seconds
        self.rps_threshold = rps_threshold
        self.pps_threshold = pps_threshold
        self.auto_block_enabled = auto_block_enabled
        
        # Sliding window tracker: ip -> deque of timestamps
        self._request_history: Dict[str, deque] = defaultdict(deque)
        self._packet_history: Dict[str, deque] = defaultdict(deque)
        self._blocked_ips: Dict[str, dict] = {} # ip -> info

    def record_request(self, source_ip: str, timestamp: Optional[float] = None) -> Tuple[int, float]:
        """Record an incoming HTTP request timestamp for an IP address"""
        now = timestamp or time.time()
        history = self._request_history[source_ip]
        history.append(now)

        # Evict timestamps outside sliding window
        cutoff = now - self.window_seconds
        while history and history[0] < cutoff:
            history.popleft()

        rps = len(history) / max(self.window_seconds, 1)
        return len(history), rps

    def record_packet(self, source_ip: str, count: int = 1, timestamp: Optional[float] = None) -> Tuple[int, float]:
        """Record network packet counts for SYN/UDP/ICMP rate tracking"""
        now = timestamp or time.time()
        history = self._packet_history[source_ip]
        for _ in range(count):
            history.append(now)

        cutoff = now - self.window_seconds
        while history and history[0] < cutoff:
            history.popleft()

        pps = len(history) / max(self.window_seconds, 1)
        return len(history), pps

    async def evaluate_ip(self, source_ip: str, protocol: str = "HTTP") -> DDoSMitigationResult:
        """
        Evaluate traffic rate for an IP address and execute mitigation if DDoS is detected.
        """
        now = time.time()
        cutoff = now - self.window_seconds

        # Prune queues
        req_queue = self._request_history.get(source_ip, deque())
        while req_queue and req_queue[0] < cutoff:
            req_queue.popleft()

        pkt_queue = self._packet_history.get(source_ip, deque())
        while pkt_queue and pkt_queue[0] < cutoff:
            pkt_queue.popleft()

        req_count = len(req_queue)
        pkt_count = len(pkt_queue)

        is_ddos = False
        attack_type = "NORMAL"
        confidence = 0.0

        if req_count >= self.rps_threshold:
            is_ddos = True
            attack_type = "HTTP_FLOOD"
            confidence = min(99.0, 85.0 + (req_count - self.rps_threshold) * 0.5)

        elif pkt_count >= self.pps_threshold:
            is_ddos = True
            attack_type = f"{protocol.upper()}_FLOOD"
            confidence = min(99.0, 85.0 + (pkt_count - self.pps_threshold) * 0.2)

        if not is_ddos:
            return DDoSMitigationResult(
                is_ddos=False,
                attack_type="NORMAL",
                confidence_score=0.0,
                target_ip=source_ip,
                action_taken="NONE",
                message=f"Traffic within normal bounds ({req_count} reqs, {pkt_count} pkts)."
            )

        # Check if already blocked
        if source_ip in self._blocked_ips:
            return DDoSMitigationResult(
                is_ddos=True,
                attack_type=attack_type,
                confidence_score=confidence,
                target_ip=source_ip,
                action_taken="ALREADY_BLOCKED",
                message=f"IP {source_ip} is already blocked on Firewall."
            )

        action_taken = "LOG_ONLY"
        msg = f"DDoS attack '{attack_type}' detected from {source_ip} (Confidence: {confidence:.1f}%)."

        # Execute Auto-Mitigation via SOAR Action if enabled and confidence >= 85%
        if self.auto_block_enabled and confidence >= 85.0:
            soar_res = await ActionEngine.execute_action(
                action_type="firewall_block",
                config={"ip": source_ip, "operation": "block", "reason": f"DDoS Auto-Mitigation: {attack_type}"},
                trigger_data={"source_ip": source_ip, "attack_type": attack_type, "confidence": confidence}
            )

            if soar_res.success:
                action_taken = "AUTO_BLOCKED"
                self._blocked_ips[source_ip] = {
                    "blocked_at": now,
                    "attack_type": attack_type,
                    "confidence": confidence,
                    "req_count": req_count,
                    "pkt_count": pkt_count,
                }
                msg += f" SOAR executed instant Firewall IP block."
            else:
                action_taken = "BLOCK_FAILED"
                msg += f" Firewall block failed: {soar_res.message}"

        logger.warn("ddos_attack_evaluated", ip=source_ip, attack_type=attack_type, confidence=confidence, action=action_taken)
        return DDoSMitigationResult(is_ddos, attack_type, confidence, source_ip, action_taken, msg)

    async def manual_mitigate(self, source_ip: str, operation: str = "block", reason: str = "Manual Analyst Mitigation") -> DDoSMitigationResult:
        """Manual 1-Click SOC Analyst Override to block or unblock an IP"""
        soar_res = await ActionEngine.execute_action(
            action_type="firewall_block",
            config={"ip": source_ip, "operation": operation, "reason": reason},
            trigger_data={"source_ip": source_ip, "manual": True}
        )

        if soar_res.success:
            if operation == "block":
                self._blocked_ips[source_ip] = {"blocked_at": time.time(), "attack_type": "MANUAL_BLOCK", "confidence": 100.0}
                act = "MANUAL_BLOCKED"
            else:
                self._blocked_ips.pop(source_ip, None)
                act = "MANUAL_UNBLOCKED"
            return DDoSMitigationResult(True, "MANUAL", 100.0, source_ip, act, f"Manual {operation} executed successfully.")
        else:
            return DDoSMitigationResult(False, "MANUAL", 0.0, source_ip, "FAILED", soar_res.message)

    def get_blocked_ips(self) -> Dict[str, dict]:
        """Return dict of currently blocked IP addresses"""
        return self._blocked_ips
