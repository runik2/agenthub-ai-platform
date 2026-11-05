from __future__ import annotations

import httpx


async def test_health_and_correlation_id(client: httpx.AsyncClient) -> None:
    response = await client.get("/health/live", headers={"x-correlation-id": "trace-demo-123"})
    assert response.status_code == 200
    assert response.headers["x-correlation-id"] == "trace-demo-123"
    assert "app;dur=" in response.headers["server-timing"]


async def test_economics_endpoint(client: httpx.AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await client.get("/api/v1/analytics/economics", headers=auth_headers)
    assert response.status_code == 200
    assert set(response.json()) == {"days", "models", "agents"}
