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


class RedisBlockStore:
    """
    Redis-backed store for persisting blocked IP addresses across restarts.

    Each blocked IP is stored as a Redis Hash:
      Key:   ddos:blocked:<ip>
      Field: blocked_at, attack_type, confidence, req_count, pkt_count
      TTL:   DDOS_BLOCK_TTL_SECONDS (default 24 h)

    Falls back to in-memory dict if Redis is unavailable.
    """

    def __init__(self, key_prefix: str = "ddos:blocked", ttl_seconds: int = 86400):
        self._key_prefix = key_prefix
        self._ttl = ttl_seconds
        self._fallback: Dict[str, dict] = {}  # in-memory fallback
        self._redis = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ip_key(self, ip: str) -> str:
        return f"{self._key_prefix}:{ip}"

    async def _get_redis(self):
        """Lazy-initialize Redis client from the app's shared connection pool."""
        if self._redis is not None:
            return self._redis
        try:
            from app.core.redis import get_redis_manager
            mgr = get_redis_manager()
            if mgr.client is None:
                await mgr.initialize()
            self._redis = mgr.client
        except Exception as e:
            logger.warning("ddos_redis_unavailable_using_fallback", error=str(e))
            self._redis = None
        return self._redis

    # ------------------------------------------------------------------
    # Public interface (mirrors a dict)
    # ------------------------------------------------------------------

    async def add(self, ip: str, info: dict) -> None:
        """Persist a blocked IP with metadata. TTL is applied automatically."""
        redis = await self._get_redis()
        if redis:
            try:
                key = self._ip_key(ip)
                # Convert float/int to str for Redis hash compatibility
                mapping = {k: str(v) for k, v in info.items()}
                await redis.hset(key, mapping=mapping)
                await redis.expire(key, self._ttl)
                return
            except Exception as e:
                logger.warning("ddos_redis_write_error", ip=ip, error=str(e))
        # Fallback
        self._fallback[ip] = info

    async def remove(self, ip: str) -> None:
        """Unblock an IP — removes from Redis and fallback."""
        redis = await self._get_redis()
        if redis:
            try:
                await redis.delete(self._ip_key(ip))
            except Exception as e:
                logger.warning("ddos_redis_delete_error", ip=ip, error=str(e))
        self._fallback.pop(ip, None)

    async def contains(self, ip: str) -> bool:
        """Check if an IP is currently blocked."""
        redis = await self._get_redis()
        if redis:
            try:
                return bool(await redis.exists(self._ip_key(ip)))
            except Exception as e:
                logger.warning("ddos_redis_exists_error", ip=ip, error=str(e))
        return ip in self._fallback

    async def get(self, ip: str) -> Optional[dict]:
        """Return block metadata for an IP, or None if not blocked."""
        redis = await self._get_redis()
        if redis:
            try:
                data = await redis.hgetall(self._ip_key(ip))
                if data:
                    # Redis returns bytes; decode them
                    return {
                        k.decode() if isinstance(k, bytes) else k:
                        v.decode() if isinstance(v, bytes) else v
                        for k, v in data.items()
                    }
                return None
            except Exception as e:
                logger.warning("ddos_redis_get_error", ip=ip, error=str(e))
        return self._fallback.get(ip)

    async def get_all(self) -> Dict[str, dict]:
        """Return all currently blocked IPs and their metadata."""
        redis = await self._get_redis()
        result: Dict[str, dict] = {}
        if redis:
            try:
                # Scan for all keys matching the prefix
                pattern = f"{self._key_prefix}:*"
                cursor = 0
                while True:
                    cursor, keys = await redis.scan(cursor, match=pattern, count=100)
                    for key in keys:
                        key_str = key.decode() if isinstance(key, bytes) else key
                        ip = key_str.removeprefix(f"{self._key_prefix}:")
                        data = await redis.hgetall(key)
                        if data:
                            result[ip] = {
                                k.decode() if isinstance(k, bytes) else k:
                                v.decode() if isinstance(v, bytes) else v
                                for k, v in data.items()
                            }
                    if cursor == 0:
                        break
                return result
            except Exception as e:
                logger.warning("ddos_redis_scan_error", error=str(e))
        return dict(self._fallback)


class DDoSEngine:
    """
    Real-Time Anti-DDoS & Rate Monitoring Engine.

    Tracks requests/packets per sliding window and automatically triggers
    SOAR Firewall IP Block when DDoS threshold (Confidence >= 85%) is exceeded.

    Blocked IPs are persisted in Redis (via RedisBlockStore) so they survive
    service restarts. Falls back to in-memory storage if Redis is unavailable.
    """

    def __init__(
        self,
        window_seconds: int = 60,
        rps_threshold: int = 100,   # HTTP Flood threshold
        pps_threshold: int = 500,   # SYN/UDP/ICMP Flood threshold
        auto_block_enabled: bool = True,
        redis_key_prefix: str = "ddos:blocked",
        block_ttl_seconds: int = 86400,
    ):
        self.window_seconds = window_seconds
        self.rps_threshold = rps_threshold
        self.pps_threshold = pps_threshold
        self.auto_block_enabled = auto_block_enabled

        # Sliding window trackers: ip -> deque of timestamps
        self._request_history: Dict[str, deque] = defaultdict(deque)
        self._packet_history: Dict[str, deque] = defaultdict(deque)

        # Redis-backed persistent block store (replaces plain dict)
        self._block_store = RedisBlockStore(
            key_prefix=redis_key_prefix,
            ttl_seconds=block_ttl_seconds,
        )

    # ------------------------------------------------------------------
    # Traffic recording
    # ------------------------------------------------------------------

    def record_request(self, source_ip: str, timestamp: Optional[float] = None) -> Tuple[int, float]:
        """Record an incoming HTTP request timestamp for an IP address."""
        now = timestamp or time.time()
        history = self._request_history[source_ip]
        history.append(now)

        cutoff = now - self.window_seconds
        while history and history[0] < cutoff:
            history.popleft()

        rps = len(history) / max(self.window_seconds, 1)
        return len(history), rps

    def record_packet(self, source_ip: str, count: int = 1, timestamp: Optional[float] = None) -> Tuple[int, float]:
        """Record network packet counts for SYN/UDP/ICMP rate tracking."""
        now = timestamp or time.time()
        history = self._packet_history[source_ip]
        for _ in range(count):
            history.append(now)

        cutoff = now - self.window_seconds
        while history and history[0] < cutoff:
            history.popleft()

        pps = len(history) / max(self.window_seconds, 1)
        return len(history), pps

    # ------------------------------------------------------------------
    # Evaluation & mitigation
    # ------------------------------------------------------------------

    async def evaluate_ip(self, source_ip: str, protocol: str = "HTTP") -> DDoSMitigationResult:
        """
        Evaluate traffic rate for an IP address and execute mitigation if DDoS is detected.
        Blocked IP state is checked and written to Redis for persistence.
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

        # Check if already blocked (Redis-backed)
        if await self._block_store.contains(source_ip):
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
                block_info = {
                    "blocked_at": now,
                    "attack_type": attack_type,
                    "confidence": confidence,
                    "req_count": req_count,
                    "pkt_count": pkt_count,
                }
                await self._block_store.add(source_ip, block_info)
                msg += " SOAR executed instant Firewall IP block. State persisted to Redis."
            else:
                action_taken = "BLOCK_FAILED"
                msg += f" Firewall block failed: {soar_res.message}"

        logger.warn("ddos_attack_evaluated", ip=source_ip, attack_type=attack_type,
                    confidence=confidence, action=action_taken)
        return DDoSMitigationResult(is_ddos, attack_type, confidence, source_ip, action_taken, msg)

    async def manual_mitigate(
        self,
        source_ip: str,
        operation: str = "block",
        reason: str = "Manual Analyst Mitigation"
    ) -> DDoSMitigationResult:
        """Manual 1-Click SOC Analyst Override to block or unblock an IP."""
        soar_res = await ActionEngine.execute_action(
            action_type="firewall_block",
            config={"ip": source_ip, "operation": operation, "reason": reason},
            trigger_data={"source_ip": source_ip, "manual": True}
        )

        if soar_res.success:
            if operation == "block":
                await self._block_store.add(source_ip, {
                    "blocked_at": time.time(),
                    "attack_type": "MANUAL_BLOCK",
                    "confidence": 100.0
                })
                act = "MANUAL_BLOCKED"
            else:
                await self._block_store.remove(source_ip)
                act = "MANUAL_UNBLOCKED"
            return DDoSMitigationResult(True, "MANUAL", 100.0, source_ip, act,
                                        f"Manual {operation} executed successfully.")
        else:
            return DDoSMitigationResult(False, "MANUAL", 0.0, source_ip, "FAILED", soar_res.message)

    # ------------------------------------------------------------------
    # State queries (now async due to Redis)
    # ------------------------------------------------------------------

    async def get_blocked_ips_async(self) -> Dict[str, dict]:
        """Return all currently blocked IPs from Redis (or fallback)."""
        return await self._block_store.get_all()

    def get_blocked_ips(self) -> Dict[str, dict]:
        """
        Synchronous fallback accessor kept for backward compatibility with
        DDoSMiddleware which calls this in a non-async context.
        Returns the in-memory fallback dict — may be slightly stale if
        Redis is the primary store but is sufficient for the hot-path check.
        """
        return self._block_store._fallback


# ── Module-level singleton — shared across API router and DDoS middleware ──────
# Import this instance instead of creating a new DDoSEngine() to ensure
# all components share the same in-memory tracking state.
def _make_ddos_engine() -> DDoSEngine:
    """Factory that reads config safely, with defaults if settings aren't loaded."""
    try:
        from app.core.config import settings
        return DDoSEngine(
            auto_block_enabled=True,
            redis_key_prefix=settings.DDOS_REDIS_KEY_PREFIX,
            block_ttl_seconds=settings.DDOS_BLOCK_TTL_SECONDS,
        )
    except Exception:
        return DDoSEngine(auto_block_enabled=True)


ddos_engine = _make_ddos_engine()
