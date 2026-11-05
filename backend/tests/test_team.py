from __future__ import annotations

import httpx


async def test_admin_can_manage_team_roles(client: httpx.AsyncClient, auth_headers: dict[str, str]) -> None:
    created = await client.post(
        "/api/v1/team",
        json={
            "email": "operator@example.com",
            "full_name": "Operator",
            "password": "operator123",
            "role": "operator",
        },
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text
    member = created.json()
    assert member["role"] == "operator"

    updated = await client.patch(
        f"/api/v1/team/{member['id']}", json={"role": "viewer", "is_active": False}, headers=auth_headers
    )
    assert updated.status_code == 200
    assert updated.json()["role"] == "viewer"
    assert updated.json()["is_active"] is False


async def test_non_admin_cannot_access_team(client: httpx.AsyncClient, auth_headers: dict[str, str]) -> None:
    created = await client.post(
        "/api/v1/team",
        json={
            "email": "manager@example.com",
            "full_name": "Manager",
            "password": "manager123",
            "role": "manager",
        },
        headers=auth_headers,
    )
    member = created.json()
    login = await client.post(
        "/api/v1/auth/login", json={"email": member["email"], "password": "manager123"}
    )
    response = await client.get(
        "/api/v1/team", headers={"Authorization": f"Bearer {login.json()['access_token']}"}
    )
    assert response.status_code == 403


async def test_viewer_cannot_change_workspace_configuration(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    created = await client.post(
        "/api/v1/team",
        json={
            "email": "viewer@example.com",
            "full_name": "Viewer",
            "password": "viewer123",
            "role": "viewer",
        },
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text
    login = await client.post(
        "/api/v1/auth/login", json={"email": "viewer@example.com", "password": "viewer123"}
    )
    viewer_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = await client.post(
        "/api/v1/workflows",
        json={"name": "Should be denied", "description": "", "enabled": True, "steps": []},
        headers=viewer_headers,
    )
    assert response.status_code == 403
