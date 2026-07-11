from datetime import UTC, datetime, timedelta
from collections import defaultdict, deque
from uuid import uuid4

from fastapi import Request
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from app.config import settings


class RedisRateLimiter:
    def __init__(self) -> None:
        self._redis = Redis.from_url(settings.redis_url, decode_responses=True)
        self._fallback_requests: dict[str, deque[datetime]] = defaultdict(deque)

    async def allow(
        self,
        request: Request,
        bucket: str,
        window_seconds: float,
        max_requests: int,
    ) -> bool:
        client = request.client
        client_ip = client.host if client else "unknown"
        key = f"rate_limit:{bucket}:{client_ip}"
        now = datetime.now(UTC)
        cutoff = now - timedelta(seconds=window_seconds)
        cutoff_ms = int(cutoff.timestamp() * 1000)
        now_ms = int(now.timestamp() * 1000)
        member = f"{now_ms}:{uuid4().hex}"

        try:
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.zremrangebyscore(key, 0, cutoff_ms)
                pipe.zcard(key)
                _, count = await pipe.execute()

            if count >= max_requests:
                return False

            await self._redis.zadd(key, {member: now_ms})
            await self._redis.expire(key, max(1, int(window_seconds)))
            return True
        except RedisConnectionError:
            timestamps = self._fallback_requests[key]
            while timestamps and timestamps[0] < cutoff:
                timestamps.popleft()

            if len(timestamps) >= max_requests:
                return False

            timestamps.append(now)
            return True


rate_limiter = RedisRateLimiter()
