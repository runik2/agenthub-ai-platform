from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Any


class RateLimiter:
    """Small fixed-window limiter with a Redis backend when available."""

    def __init__(self, redis_url: str | None = None) -> None:
        self._redis_url = redis_url
        self._redis: Any = None
        self._local: dict[str, deque[float]] = defaultdict(deque)

    async def _redis_client(self) -> Any:
        if not self._redis_url:
            return None
        if self._redis is None:
            from redis.asyncio import from_url

            self._redis = from_url(self._redis_url, decode_responses=True)
        return self._redis

    async def check(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int, int]:
        now = time.monotonic()
        try:
            redis = await self._redis_client()
            if redis is not None:
                bucket = f"agenthub:ratelimit:{key}"
                count = int(await redis.incr(bucket))
                if count == 1:
                    await redis.expire(bucket, window_seconds)
                ttl = max(1, int(await redis.ttl(bucket)))
                return count <= limit, max(0, limit - count), ttl
        except Exception:
            # A Redis outage must not remove the protection entirely.
            self._redis = None

        events = self._local[key]
        cutoff = now - window_seconds
        while events and events[0] <= cutoff:
            events.popleft()
        allowed = len(events) < limit
        if allowed:
            events.append(now)
        retry_after = max(1, int(events[0] + window_seconds - now)) if events else window_seconds
        return allowed, max(0, limit - len(events)), retry_after

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    def reset_local(self) -> None:
        """Reset the process-local fallback (used by isolated local app instances/tests)."""
        self._local.clear()
