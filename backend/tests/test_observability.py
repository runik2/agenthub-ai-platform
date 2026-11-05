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


async def test_readiness_reports_queue_health(client: httpx.AsyncClient, monkeypatch) -> None:
    from app.api.v1 import health

    class HealthyQueue:
        async def health(self) -> bool:
            return True

    monkeypatch.setattr(health, "get_queue", lambda: HealthyQueue())
    response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["queue"] == "ok"
