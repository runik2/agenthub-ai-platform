from __future__ import annotations

import httpx

from tests.test_agents import AGENT_PAYLOAD


async def test_evaluation_case_crud_boundary(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    agent_response = await client.post(
        "/api/v1/agents", json={**AGENT_PAYLOAD, "name": "Eval Agent"}, headers=auth_headers
    )
    agent = agent_response.json()
    created = await client.post(
        "/api/v1/evaluations/cases",
        json={"agent_id": agent["id"], "name": "Greeting", "prompt": "Say hello", "expected": "hello"},
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text
    cases = await client.get("/api/v1/evaluations/cases", headers=auth_headers)
    assert cases.status_code == 200
    assert cases.json()[0]["expected"] == "hello"
