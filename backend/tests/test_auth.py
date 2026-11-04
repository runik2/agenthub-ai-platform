from __future__ import annotations

import httpx


async def test_setup_status_reports_existing_admin(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/auth/setup-status")
    assert response.status_code == 200
    assert response.json() == {"needs_setup": False}


async def test_setup_is_rejected_when_admin_exists(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/setup",
        json={"email": "second@test.local", "password": "another-pass", "full_name": "Second"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SETUP_ALREADY_DONE"


async def test_login_and_me(client: httpx.AsyncClient) -> None:
    login = await client.post(
        "/api/v1/auth/login", json={"email": "admin@test.local", "password": "admin12345"}
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    assert login.json()["token_type"] == "bearer"

    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "admin@test.local"
    assert me.json()["role"] == "admin"
    assert "hashed_password" not in me.json()


async def test_login_with_wrong_password(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login", json={"email": "admin@test.local", "password": "nope-nope"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_protected_route_requires_token(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/agents")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


async def test_invalid_token_is_rejected(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/agents", headers={"Authorization": "Bearer not-a-token"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
