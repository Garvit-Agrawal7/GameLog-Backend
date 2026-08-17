import asyncio
import json
import secrets
import time
from typing import Any, Callable

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.config import settings

ACQUIRE_LOCK_SCRIPT = """
if redis.call('SET', KEYS[1], ARGV[1], 'NX', 'PX', ARGV[2]) then
    return 1
end
return 0
"""

RELEASE_LOCK_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""


class RedisCache:
    DEFAULT_TTL = 604800 # 7 day cache time to live
    LOCK_TTL_MS = 5000
    WAIT_POLL_MS = 100

    def __init__(self) -> None:
        self._redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=50,
        )
        self._acquire_lock = self._redis.register_script(ACQUIRE_LOCK_SCRIPT)
        self._release_lock = self._redis.register_script(RELEASE_LOCK_SCRIPT)

    async def get_or_fetch(self, cache_key: str, fetch_fn: Callable[[], Any], ttl: int = DEFAULT_TTL) -> Any:
        """Get a value from cache or fetch it if not present."""
        try:
            cached = await self._redis.get(cache_key)
            if cached is not None:
                return json.loads(cached)
        except RedisError:
            # cache unavailable, skip locking entirely and fetch directly
            return await fetch_fn()

        return await self._load_cache(cache_key, fetch_fn, ttl)

    async def _load_cache(self, cache_key: str, fetch_fn: Callable[[], Any], ttl: int) -> Any:
        """Load the cache with locking to prevent stampedes."""
        lock_key = f"lock:{cache_key}"
        token = secrets.token_hex(8)

        try:
            acquired = await self._acquire_lock(
                keys=[lock_key], args=[token, self.LOCK_TTL_MS]
            )
        except RedisError:
            return await fetch_fn()

        if acquired:
            try:
                data = await fetch_fn()
                try:
                    await self._redis.set(cache_key, json.dumps(data), ex=ttl)
                except RedisError:
                    pass  # cache write failed, still return fresh data
                return data
            finally:
                try:
                    await self._release_lock(keys=[lock_key], args=[token])
                except RedisError:
                    pass

        # Another caller is loading. Poll briefly for the cache to populate.
        deadline = time.monotonic() + (self.LOCK_TTL_MS / 1000.0)
        while time.monotonic() < deadline:
            await asyncio.sleep(self.WAIT_POLL_MS / 1000.0)
            try:
                cached = await self._redis.get(cache_key)
            except RedisError:
                break
            if cached is not None:
                return json.loads(cached)

        # Lock holder never populated the cache in time, fetch directly.
        return await fetch_fn()

    async def invalidate(self, cache_key: str) -> None:
        try:
            await self._redis.delete(cache_key)
        except RedisError:
            pass


redis_cache = RedisCache()