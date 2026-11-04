from __future__ import annotations

import httpx

from tests.conftest import ollama_answer, raw_usage_rows


async def _prepare(client: httpx.AsyncClient, headers: dict[str, str], price_in=0.0, price_out=0.0) -> dict:
    provider = await client.post(
        "/api/v1/providers",
        json={
            "name": "Mock Ollama",
            "kind": "ollama",
            "base_url": "http://mock-ollama:11434",
            "default_model": "llama3.2:3b",
            "input_price_per_1m": price_in,
            "output_price_per_1m": price_out,
        },
        headers=headers,
    )
    assert provider.status_code == 201, provider.text
    agent = await client.post(
        "/api/v1/agents",
        json={
            "name": "Chat Agent",
            "system_prompt": "You are helpful.",
            "provider_id": provider.json()["id"],
            "model_name": "llama3.2:3b",
            "status": "active",
        },
        headers=headers,
    )
    assert agent.status_code == 201, agent.text
    conversation = await client.post(
        "/api/v1/conversations", json={"agent_id": agent.json()["id"]}, headers=headers
    )
    assert conversation.status_code == 201, conversation.text
    return {
        "provider": provider.json(),
        "agent": agent.json(),
        "conversation": conversation.json(),
    }


async def test_chat_records_history_and_usage(
    client: httpx.AsyncClient, auth_headers: dict[str, str], mock_llm
) -> None:
    context = await _prepare(client, auth_headers, price_in=3.0, price_out=6.0)
    conversation_id = context["conversation"]["id"]

    response = await client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Hello there"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["assistant_message"]["content"] == "Mock answer from the model."
    assert body["usage"]["tokens_in"] == 42
    assert body["usage"]["tokens_out"] == 11
    assert body["usage"]["total_tokens"] == 53
    # 42/1M*3 + 11/1M*6
    assert body["usage"]["cost"] == 0.000192
    assert body["usage"]["model_name"] == "llama3.2:3b"

    detail = await client.get(f"/api/v1/conversations/{conversation_id}", headers=auth_headers)
    assert detail.status_code == 200
    messages = detail.json()["messages"]
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert detail.json()["message_count"] == 2
    assert detail.json()["total_tokens"] == 53
    assert detail.json()["title"] == "Hello there"

    rows = await raw_usage_rows()
    success = [row for row in rows if row["status"] == "ok" and row["agent_id"] == context["agent"]["id"]]
    assert len(success) == 1
    assert success[0]["tokens_in"] == 42
    assert success[0]["cost"] == 0.000192


async def test_chat_uses_system_prompt_and_history(
    client: httpx.AsyncClient, auth_headers: dict[str, str], mock_llm
) -> None:
    context = await _prepare(client, auth_headers)
    conversation_id = context["conversation"]["id"]
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        seen.append(json.loads(request.content))
        return ollama_answer(content=f"answer #{len(seen)}")

    mock_llm["handler"] = handler

    for text in ("first question", "second question"):
        response = await client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"content": text},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text

    second_payload = seen[1]
    roles = [message["role"] for message in second_payload["messages"]]
    assert roles[0] == "system"
    assert second_payload["messages"][0]["content"] == "You are helpful."
    assert roles.count("user") == 2
    assert roles.count("assistant") == 1


async def test_provider_failure_is_reported_not_swallowed(
    client: httpx.AsyncClient, auth_headers: dict[str, str], mock_llm
) -> None:
    context = await _prepare(client, auth_headers)
    conversation_id = context["conversation"]["id"]
    mock_llm["handler"] = lambda request: httpx.Response(503, content=b'{"error":"model loading"}')

    response = await client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Are you there?"},
        headers=auth_headers,
    )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "PROVIDER_ERROR"

    detail = await client.get(f"/api/v1/conversations/{conversation_id}", headers=auth_headers)
    assert len(detail.json()["messages"]) == 1  # only the user message is stored

    rows = await raw_usage_rows()
    failed = [row for row in rows if row["status"] == "error" and row["agent_id"] == context["agent"]["id"]]
    assert failed and failed[0]["error_code"] == "PROVIDER_ERROR"


async def test_agent_without_provider_is_rejected(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    agent = await client.post(
        "/api/v1/agents",
        json={"name": "No Provider", "system_prompt": "hi", "status": "active"},
        headers=auth_headers,
    )
    conversation = await client.post(
        "/api/v1/conversations", json={"agent_id": agent.json()["id"]}, headers=auth_headers
    )
    response = await client.post(
        f"/api/v1/conversations/{conversation.json()['id']}/messages",
        json={"content": "hello"},
        headers=auth_headers,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "AGENT_NO_PROVIDER"
