from __future__ import annotations

import httpx
import pytest

from app.core.rate_limit import RateLimiter


@pytest.mark.asyncio
async def test_memory_rate_limiter_returns_retry_window() -> None:
    limiter = RateLimiter()
    assert await limiter.check("test", 2, 60) == (True, 1, 60)
    allowed, remaining, retry_after = await limiter.check("test", 2, 60)
    assert allowed and remaining == 0 and 1 <= retry_after <= 60
    allowed, remaining, retry_after = await limiter.check("test", 2, 60)
    assert not allowed
    assert remaining == 0
    assert 1 <= retry_after <= 60


async def test_public_webhook_endpoint_is_rate_limited(client: httpx.AsyncClient) -> None:
    responses = [
        await client.post("/api/v1/webhooks/incoming/missing-rate-limit", content=b"{}")
        for _ in range(61)
    ]
    assert all(response.status_code == 404 for response in responses[:60])
    assert responses[-1].status_code == 429
    assert responses[-1].headers["Retry-After"]
