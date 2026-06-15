"""
GeoIP Enrichment Service

Local GeoIP database for IP enrichment.
Caches results in Redis for performance.
"""
from __future__ import annotations

from typing import Optional, Dict, Any
import geoip2.database
import redis.asyncio as aioredis
import structlog
import json

logger = structlog.get_logger()


class GeoIPService:
    """
    Local GeoIP enrichment service.
    
    Uses MaxMind GeoIP2 database or similar.
    Caches results in Redis.
    """

    def __init__(
        self,
        db_path: str = "/usr/share/GeoIP/GeoLite2-City.mmdb",
        redis_url: str = "redis://localhost:6379/0",
        cache_ttl: int = 86400,  # 24 hours
    ):
        self.db_path = db_path
        self.redis_url = redis_url
        self.cache_ttl = cache_ttl
        self._reader: Optional[geoip2.database.Reader] = None
        self._redis: Optional[aioredis.Redis] = None

    async def _get_reader(self) -> Optional[geoip2.database.Reader]:
        """Get or initialize GeoIP database reader."""
        if self._reader is None:
            try:
                import os
                if not os.path.exists(self.db_path):
                    # Silently skip — GeoIP DB is optional
                    return None
                self._reader = geoip2.database.Reader(self.db_path)
                logger.info("geoip_db_loaded", path=self.db_path)
            except Exception as e:
                logger.warning("geoip_db_unavailable", error=str(e), path=self.db_path)
                return None
        return self._reader

    async def _get_redis(self) -> Optional[aioredis.Redis]:
        """Get or initialize Redis connection."""
        if self._redis is None:
            try:
                self._redis = await aioredis.from_url(self.redis_url)
            except Exception as e:
                await logger.aerror("geoip_redis_error", error=str(e))
                return None
        return self._redis

    async def lookup(self, ip_address: str) -> Optional[Dict[str, Any]]:
        """
        Lookup IP address geolocation.
        
        Uses cache first, falls back to database.
        
        Args:
            ip_address: IPv4 or IPv6 address
            
        Returns:
            GeoIP data dict with country_code, city, etc. or None
        """
        if not ip_address:
            return None

        try:
            # Check cache
            redis = await self._get_redis()
            if redis:
                cache_key = f"geoip:{ip_address}"
                cached = await redis.get(cache_key)
                if cached:
                    return json.loads(cached)

            # Query database
            reader = await self._get_reader()
            if not reader:
                return None

            response = reader.city(ip_address)
            
            result = {
                "ip": ip_address,
                # Use 'country' key — this is what EventNormalizer expects
                "country": response.country.iso_code,
                "country_code": response.country.iso_code,
                "country_name": response.country.name,
                "city": response.city.name,
                "latitude": response.location.latitude,
                "longitude": response.location.longitude,
                "timezone": response.location.time_zone,
            }

            # Cache result
            if redis:
                await redis.setex(
                    cache_key,
                    self.cache_ttl,
                    json.dumps(result),
                )

            return result

        except Exception as e:
            await logger.adebug("geoip_lookup_error", ip=ip_address, error=str(e))
            return None

    async def close(self) -> None:
        """Close connections."""
        if self._reader:
            self._reader.close()
        if self._redis:
            await self._redis.close()
