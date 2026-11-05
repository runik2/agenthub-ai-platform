from __future__ import annotations

import httpx

from app.core.security import totp_code


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
    refresh_token = login.json()["refresh_token"]
    assert login.json()["token_type"] == "bearer"

    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "admin@test.local"
    assert me.json()["role"] == "admin"
    assert "hashed_password" not in me.json()

    refreshed = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"]
    reused = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert reused.status_code == 401


async def test_logout_all_revokes_refresh_sessions(client: httpx.AsyncClient) -> None:
    login = await client.post(
        "/api/v1/auth/login", json={"email": "admin@test.local", "password": "admin12345"}
    )
    token = login.json()["access_token"]
    refresh_token = login.json()["refresh_token"]
    response = await client.post("/api/v1/auth/logout-all", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    revoked = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert revoked.status_code == 401


async def test_password_change_revokes_sessions(client: httpx.AsyncClient) -> None:
    admin_login = await client.post(
        "/api/v1/auth/login", json={"email": "admin@test.local", "password": "admin12345"}
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
    created = await client.post(
        "/api/v1/team",
        json={
            "email": "password-test@example.com",
            "full_name": "Password Test",
            "password": "old-pass123",
            "role": "viewer",
        },
        headers=admin_headers,
    )
    assert created.status_code == 201
    login = await client.post(
        "/api/v1/auth/login", json={"email": "password-test@example.com", "password": "old-pass123"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    old_refresh = login.json()["refresh_token"]
    changed = await client.post(
        "/api/v1/auth/password",
        json={"current_password": "old-pass123", "new_password": "new-pass123"},
        headers=headers,
    )
    assert changed.status_code == 200
    assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})).status_code == 401
    relogin = await client.post(
        "/api/v1/auth/login", json={"email": "password-test@example.com", "password": "new-pass123"}
    )
    assert relogin.status_code == 200


async def test_two_factor_setup_and_login_gate(client: httpx.AsyncClient) -> None:
    admin = await client.post(
        "/api/v1/auth/login", json={"email": "admin@test.local", "password": "admin12345"}
    )
    created = await client.post(
        "/api/v1/team",
        json={
            "email": "two-factor@example.com",
            "full_name": "Two Factor",
            "password": "twofactor123",
            "role": "viewer",
        },
        headers={"Authorization": f"Bearer {admin.json()['access_token']}"},
    )
    assert created.status_code == 201
    login = await client.post(
        "/api/v1/auth/login", json={"email": "two-factor@example.com", "password": "twofactor123"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post("/api/v1/auth/2fa/setup", headers=headers)
    assert setup.status_code == 200
    secret = setup.json()["secret"]
    code = totp_code(secret)
    enabled = await client.post("/api/v1/auth/2fa/enable", json={"code": code}, headers=headers)
    assert enabled.status_code == 200
    blocked = await client.post(
        "/api/v1/auth/login", json={"email": "two-factor@example.com", "password": "twofactor123"}
    )
    assert blocked.status_code == 401
    allowed = await client.post(
        "/api/v1/auth/login",
        json={"email": "two-factor@example.com", "password": "twofactor123", "otp_code": code},
    )
    assert allowed.status_code == 200


async def test_login_is_temporarily_locked_after_five_failures(client: httpx.AsyncClient) -> None:
    admin = await client.post(
        "/api/v1/auth/login", json={"email": "admin@test.local", "password": "admin12345"}
    )
    created = await client.post(
        "/api/v1/team",
        json={
            "email": "lock-test@example.com",
            "full_name": "Lock Test",
            "password": "correct123",
            "role": "viewer",
        },
        headers={"Authorization": f"Bearer {admin.json()['access_token']}"},
    )
    assert created.status_code == 201
    for _ in range(5):
        failed = await client.post(
            "/api/v1/auth/login", json={"email": "lock-test@example.com", "password": "wrong-password"}
        )
        assert failed.status_code == 401
    locked = await client.post(
        "/api/v1/auth/login", json={"email": "lock-test@example.com", "password": "correct123"}
    )
    assert locked.status_code == 429


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
