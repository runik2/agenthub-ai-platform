from __future__ import annotations

from urllib.parse import parse_qs, urlparse

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
    login = await client.post("/api/v1/auth/login", json={"email": member["email"], "password": "manager123"})
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


async def test_manager_can_work_with_admin_workspace_resources(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    workflow = await client.post(
        "/api/v1/workflows",
        json={"name": "Shared team workflow", "description": "", "enabled": True, "steps": []},
        headers=auth_headers,
    )
    assert workflow.status_code == 201, workflow.text
    created = await client.post(
        "/api/v1/team",
        json={
            "email": "workspace-manager@example.com",
            "full_name": "Workspace Manager",
            "password": "manager123",
            "role": "manager",
        },
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text
    login = await client.post(
        "/api/v1/auth/login", json={"email": "workspace-manager@example.com", "password": "manager123"}
    )
    manager_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    listed = await client.get("/api/v1/workflows", headers=manager_headers)
    assert listed.status_code == 200
    assert any(item["id"] == workflow.json()["id"] for item in listed.json())


async def test_invitation_link_creates_workspace_member_once(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    created = await client.post(
        "/api/v1/team/invitations",
        json={"email": "invited@example.com", "role": "operator"},
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text
    invite_url = created.json()["invite_url"]
    token = parse_qs(urlparse(invite_url).query)["invite_token"][0]
    accepted = await client.post(
        "/api/v1/team/invitations/accept",
        json={"token": token, "full_name": "Invited User", "password": "invite-pass123"},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["email"] == "invited@example.com"
    reused = await client.post(
        "/api/v1/team/invitations/accept",
        json={"token": token, "full_name": "Another User", "password": "invite-pass123"},
    )
    assert reused.status_code == 400
