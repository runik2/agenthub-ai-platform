from __future__ import annotations

import httpx


async def test_prometheus_metrics_exposes_request_counters(client: httpx.AsyncClient) -> None:
    live = await client.get("/health/live")
    assert live.status_code == 200
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert "agenthub_http_requests_total" in response.text
    assert 'path="/health/live"' in response.text
    assert response.headers["content-type"].startswith("text/plain")
