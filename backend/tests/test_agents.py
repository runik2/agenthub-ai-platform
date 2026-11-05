from __future__ import annotations

import httpx

AGENT_PAYLOAD = {
    "name": "Support Bot",
    "description": "Answers questions",
    "system_prompt": "You are a support agent.",
    "greeting": "Hi!",
    "temperature": 0.4,
    "max_tokens": 512,
    "status": "active",
    "avatar_color": "#3B82F6",
    "tags": ["support", "demo"],
}


async def create_agent(client: httpx.AsyncClient, headers: dict[str, str], name: str = "Support Bot") -> dict:
    payload = {**AGENT_PAYLOAD, "name": name}
    response = await client.post("/api/v1/agents", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def test_agent_crud_flow(client: httpx.AsyncClient, auth_headers: dict[str, str]) -> None:
    agent = await create_agent(client, auth_headers, "CRM Assistant")
    assert agent["slug"] == "crm-assistant"
    assert agent["tags"] == ["support", "demo"]

    listing = await client.get("/api/v1/agents", headers=auth_headers)
    assert listing.status_code == 200
    assert listing.json()["total"] >= 1
    assert any(item["id"] == agent["id"] for item in listing.json()["items"])

    detail = await client.get(f"/api/v1/agents/{agent['id']}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["system_prompt"] == "You are a support agent."

    updated = await client.patch(
        f"/api/v1/agents/{agent['id']}",
        json={"name": "CRM Helper", "temperature": 1.2},
        headers=auth_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "CRM Helper"
    assert updated.json()["slug"] == "crm-helper"
    assert updated.json()["temperature"] == 1.2

    deleted = await client.delete(f"/api/v1/agents/{agent['id']}", headers=auth_headers)
    assert deleted.status_code == 200

    missing = await client.get(f"/api/v1/agents/{agent['id']}", headers=auth_headers)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "AGENT_NOT_FOUND"


async def test_slug_collision_gets_suffix(client: httpx.AsyncClient, auth_headers: dict[str, str]) -> None:
    first = await create_agent(client, auth_headers, "Duplicate Name")
    second = await create_agent(client, auth_headers, "Duplicate Name")
    assert first["slug"] == "duplicate-name"
    assert second["slug"] == "duplicate-name-2"


async def test_prompt_history_and_restore(client: httpx.AsyncClient, auth_headers: dict[str, str]) -> None:
    agent = await create_agent(client, auth_headers, "Versioned Agent")
    original = agent["system_prompt"]
    changed = await client.patch(
        f"/api/v1/agents/{agent['id']}",
        json={"system_prompt": "You are the new version."},
        headers=auth_headers,
    )
    assert changed.status_code == 200

    history = await client.get(f"/api/v1/agents/{agent['id']}/prompt-versions", headers=auth_headers)
    assert history.status_code == 200
    assert [item["version"] for item in history.json()] == [2, 1]
    assert history.json()[0]["author_name"]
    diff = await client.get(
        f"/api/v1/agents/{agent['id']}/prompt-versions/diff",
        params={"from_version": 1, "to_version": 2},
        headers=auth_headers,
    )
    assert diff.status_code == 200
    assert "You are the new version." in diff.json()["unified_diff"]
    first = next(item for item in history.json() if item["version"] == 1)
    restored = await client.post(
        f"/api/v1/agents/{agent['id']}/prompt-versions/{first['id']}/restore",
        headers=auth_headers,
    )
    assert restored.status_code == 200
    assert restored.json()["system_prompt"] == original


async def test_six_templates_and_creation_from_template(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    templates = await client.get("/api/v1/agents/templates", headers=auth_headers)
    assert templates.status_code == 200
    slugs = [item["slug"] for item in templates.json()]
    assert len(slugs) == 6
    assert "code-reviewer" in slugs

    created = await client.post("/api/v1/agents/from-template/code-reviewer", headers=auth_headers)
    assert created.status_code == 201
    body = created.json()
    assert body["template_slug"] == "code-reviewer"
    assert body["status"] == "draft"
    assert body["system_prompt"]


async def test_duplicate_agent(client: httpx.AsyncClient, auth_headers: dict[str, str]) -> None:
    agent = await create_agent(client, auth_headers, "Clone Source")
    clone = await client.post(f"/api/v1/agents/{agent['id']}/duplicate", headers=auth_headers)
    assert clone.status_code == 201
    assert clone.json()["name"] == "Clone Source (copy)"
    assert clone.json()["id"] != agent["id"]


async def test_delete_is_blocked_while_conversations_exist(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    agent = await create_agent(client, auth_headers, "Has Chats")
    conversation = await client.post(
        "/api/v1/conversations", json={"agent_id": agent["id"]}, headers=auth_headers
    )
    assert conversation.status_code == 201

    blocked = await client.delete(f"/api/v1/agents/{agent['id']}", headers=auth_headers)
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "AGENT_HAS_CONVERSATIONS"

    forced = await client.delete(f"/api/v1/agents/{agent['id']}?force=true", headers=auth_headers)
    assert forced.status_code == 200


async def test_validation_error_shape(client: httpx.AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await client.post("/api/v1/agents", json={"name": ""}, headers=auth_headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["details"]["fields"]
