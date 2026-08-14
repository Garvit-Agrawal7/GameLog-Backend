import time
from logging import getLogger

from fastapi import HTTPException, Request, status
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.config import settings


logger = getLogger(__name__)


class RedisRateLimiter:
    LUA_SCRIPT = """
    local key = KEYS[1]
    local capacity = tonumber(ARGV[1])
    local refill_rate = tonumber(ARGV[2])
    local now = tonumber(ARGV[3])
    local ttl_seconds = tonumber(ARGV[4])

    local function load_bucket(key, capacity)
        local data = redis.call('HGETALL', key)
        local tokens = capacity
        local last_refill = now

        if #data > 0 then
            local fields = {}
            for i = 1, #data, 2 do
                fields[data[i]] = data[i + 1]
            end
            tokens = tonumber(fields['tokens']) or capacity
            last_refill = tonumber(fields['last_refill']) or now
        end

        return tokens, last_refill
    end

    local function refill(tokens, last_refill, capacity, refill_rate)
        local elapsed = math.max(0, now - last_refill)
        tokens = math.min(capacity, tokens + elapsed * refill_rate)
        return tokens
    end

    local function persist_bucket(key, tokens, capacity, refill_rate)
        redis.call('HSET', key, 'tokens', tostring(tokens), 'last_refill', tostring(now))

        local computed_ttl = ttl_seconds
        if refill_rate > 0 then
            computed_ttl = math.ceil(capacity / refill_rate) + 1
        end
        redis.call('EXPIRE', key, computed_ttl)
    end

    local tokens, last_refill = load_bucket(key, capacity)
    tokens = refill(tokens, last_refill, capacity, refill_rate)

    if tokens >= 1 then
        persist_bucket(key, tokens - 1, capacity, refill_rate)
        return 1
    end

    persist_bucket(key, tokens, capacity, refill_rate)
    return 0
    """

    DEFAULT_CAPACITY = 12.0
    DEFAULT_REFILL_RATE = 6.0
    IGDB_LOCAL_CAPACITY = 6.0
    IGDB_LOCAL_REFILL_RATE = 2.0
    BUCKET_TTL = 60

    def __init__(self) -> None:
        self._redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=50,
        )
        self._script = self._redis.register_script(self.LUA_SCRIPT)
        self._fallback_buckets: dict[str, tuple[float, float]] = {}

    async def ping(self) -> bool:
        try:
            return bool(await self._redis.ping())
        except RedisError:
            return False

    async def allow(self, request: Request, bucket: str) -> bool:
        """Check if a request is allowed based on the Redis toke bucket rate limit."""
        user_key = self._resolve_user_key(request, bucket)
        if not user_key:
            return False
        key = f"rate_limit:{bucket}:user:{user_key}"
        capacity, refill_rate = self._resolve_policy(bucket)
        now = time.time()

        try:
            result = await self._script(
                keys=[key],
                args=[capacity, refill_rate, now, self.BUCKET_TTL],
            )
            return bool(result)
        except RedisError as exc:
            logger.warning(
                "Redis rate limiting failed for bucket=%s key=%s, falling back to in-memory limiter: %s",
                bucket, key, exc,
            )
            return self._fallback_allow(key, capacity, refill_rate, now)

    def _fallback_allow(self, key: str, capacity: float, refill_rate: float, now: float) -> bool:
        """Fallback rate limiting using in-memory token bucket when Redis is unavailable."""
        tokens, _ = self._refill_bucket(key, capacity, refill_rate, now)

        if tokens < 1:
            self._fallback_buckets[key] = (tokens, now)
            return False

        self._fallback_buckets[key] = (tokens - 1, now)
        return True

    def _resolve_policy(self, bucket: str) -> tuple[float, float]:
        """Finds the rate limit to be applied based on the bucket name. Returns a tuple of (capacity, refill_rate)."""
        if bucket.startswith("igdb"):
            return self.IGDB_LOCAL_CAPACITY, self.IGDB_LOCAL_REFILL_RATE
        return self.DEFAULT_CAPACITY, self.DEFAULT_REFILL_RATE

    @staticmethod
    def _resolve_user_key(request: Request, bucket: str) -> str:
        """Resolves a unique key for the user making the request. This is used to track rate limits per user."""
        if bucket.startswith("igdb"):
            forwarded_for = request.headers.get("authorization")
            if forwarded_for:
                return forwarded_for.split(" ", 1)[1].strip()
            else:
                return ""

        client_host = request.client.host if request.client else None
        return client_host

    def _refill_bucket(self, key: str, capacity: float, refill_rate: float, now: float) -> tuple[float, float]:
        """Refills the token bucket for the given key based on the elapsed time since the last refill. (in-memory fallback)"""
        tokens, last_refill = self._fallback_buckets.get(key, (capacity, now))
        elapsed = max(0.0, now - last_refill)
        tokens = min(capacity, tokens + elapsed * refill_rate)
        return tokens, now

rate_limiter = RedisRateLimiter()

DEFAULT_BUCKET = "app"
IGDB_BUCKET = "igdb"

async def allow_default_request(request: Request) -> bool:
    return await rate_limiter.allow(request, DEFAULT_BUCKET)


async def enforce_default_limit(request: Request) -> None:
    if not await allow_default_request(request):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests")

async def allow_igdb_request(request: Request) -> bool:
    return await rate_limiter.allow(request, IGDB_BUCKET)
