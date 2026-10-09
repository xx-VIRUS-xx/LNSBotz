import json
from typing import Any
import redis.asyncio as aioredis
from core.config import settings


_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


class Cache:
    def __init__(self, prefix: str = "", ttl: int = settings.REDIS_CACHE_TTL):
        self.prefix = prefix
        self.ttl = ttl

    def _key(self, key: str) -> str:
        return f"{self.prefix}:{key}" if self.prefix else key

    async def get(self, key: str) -> Any | None:
        r = await get_redis()
        val = await r.get(self._key(key))
        return json.loads(val) if val else None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        r = await get_redis()
        await r.setex(self._key(key), ttl or self.ttl, json.dumps(value, default=str))

    async def delete(self, key: str) -> None:
        r = await get_redis()
        await r.delete(self._key(key))

    async def exists(self, key: str) -> bool:
        r = await get_redis()
        return bool(await r.exists(self._key(key)))

    async def increment(self, key: str, amount: int = 1) -> int:
        r = await get_redis()
        return await r.incrby(self._key(key), amount)

    async def expire(self, key: str, ttl: int) -> None:
        r = await get_redis()
        await r.expire(self._key(key), ttl)


class RateLimiter:
    """Sliding window rate limiter backed by Redis."""

    async def is_allowed(self, user_id: str, limit: int, window_seconds: int = 60) -> bool:
        r = await get_redis()
        key = f"ratelimit:{user_id}:{window_seconds}"
        current = await r.incr(key)
        if current == 1:
            await r.expire(key, window_seconds)
        return current <= limit

    async def get_remaining(self, user_id: str, limit: int, window_seconds: int = 60) -> int:
        r = await get_redis()
        key = f"ratelimit:{user_id}:{window_seconds}"
        current = int(await r.get(key) or 0)
        return max(0, limit - current)


rate_limiter = RateLimiter()
