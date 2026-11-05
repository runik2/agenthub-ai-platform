from __future__ import annotations

import httpx


async def test_provider_connections_are_scoped_to_the_workspace(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    provider = await client.post(
        "/api/v1/providers",
        json={
            "name": "Private provider",
            "kind": "ollama",
            "base_url": "http://private-ollama:11434",
            "default_model": "llama3.2:3b",
        },
        headers=auth_headers,
    )
    assert provider.status_code == 201, provider.text

    member = await client.post(
        "/api/v1/team",
        json={
            "email": "provider-viewer@example.com",
            "full_name": "Provider Viewer",
            "password": "viewer123",
            "role": "viewer",
        },
        headers=auth_headers,
    )
    assert member.status_code == 201, member.text
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "provider-viewer@example.com", "password": "viewer123"},
    )
    viewer_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    listed = await client.get("/api/v1/providers", headers=viewer_headers)
    assert listed.status_code == 200
    assert listed.json()["items"] == []
    hidden = await client.get(f"/api/v1/providers/{provider.json()['id']}", headers=viewer_headers)
    assert hidden.status_code == 404
