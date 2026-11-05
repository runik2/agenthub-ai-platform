from __future__ import annotations

import httpx

TOOL = {
    "name": "CRM webhook",
    "description": "Creates a CRM lead",
    "kind": "webhook",
    "method": "POST",
    "base_url": "https://crm.example.com",
    "allowed_path": "/api/leads",
    "requires_approval": True,
}


async def test_tools_are_allowlisted_and_owner_scoped(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    created = await client.post("/api/v1/tools", json=TOOL, headers=auth_headers)
    assert created.status_code == 201, created.text
    tool = created.json()
    assert tool["base_url"] == TOOL["base_url"]
    assert tool["requires_approval"] is True

    listing = await client.get("/api/v1/tools", headers=auth_headers)
    assert listing.status_code == 200
    assert any(item["id"] == tool["id"] for item in listing.json())
    journal = await client.get("/api/v1/tools/runs", headers=auth_headers)
    assert journal.status_code == 200
    assert isinstance(journal.json(), list)

    updated = await client.patch(
        f"/api/v1/tools/{tool['id']}", json={"is_active": False}, headers=auth_headers
    )
    assert updated.status_code == 200
    assert updated.json()["is_active"] is False

    deleted = await client.delete(f"/api/v1/tools/{tool['id']}", headers=auth_headers)
    assert deleted.status_code == 204


async def test_tool_refuses_private_or_unbounded_targets(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    private = await client.post(
        "/api/v1/tools", json={**TOOL, "base_url": "http://127.0.0.1:8000"}, headers=auth_headers
    )
    assert private.status_code == 422
    unsafe_path = await client.post(
        "/api/v1/tools", json={**TOOL, "allowed_path": "https://evil.example"}, headers=auth_headers
    )
    assert unsafe_path.status_code == 422


async def test_tool_catalog_contains_safe_starters(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.get("/api/v1/tools/catalog", headers=auth_headers)
    assert response.status_code == 200, response.text
    catalog = response.json()
    assert {item["id"] for item in catalog} >= {
        "telegram-bridge",
        "gmail-bridge",
        "crm-webhook",
        "notion-bridge",
        "google-calendar-bridge",
    }
    assert all("token" not in item["base_url"].lower() for item in catalog)
    assert all(item["base_url"].startswith("https://") for item in catalog)
