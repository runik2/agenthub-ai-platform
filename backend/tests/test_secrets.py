from __future__ import annotations

import httpx
from sqlalchemy import select

from app.db.models import LLMProvider
from app.db.session import get_session_factory

SECRET = "sk-live-very-secret-key-1234567890"


async def test_api_key_never_leaves_the_backend(client: httpx.AsyncClient, auth_headers: dict[str, str]) -> None:
    created = await client.post(
        "/api/v1/providers",
        json={
            "name": "OpenAI Compatible",
            "kind": "openai_compatible",
            "base_url": "https://api.example.com/v1",
            "api_key": SECRET,
            "default_model": "gpt-4o-mini",
        },
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text
    body = created.json()
    provider_id = body["id"]

    assert body["has_api_key"] is True
    assert body["api_key_hint"] == "***7890"
    serialized = created.text + (await client.get("/api/v1/providers", headers=auth_headers)).text
    serialized += (await client.get(f"/api/v1/providers/{provider_id}", headers=auth_headers)).text
    assert SECRET not in serialized
    assert "api_key_encrypted" not in serialized
    assert "sk-live" not in serialized

    async with get_session_factory()() as session:
        provider = await session.scalar(select(LLMProvider).where(LLMProvider.id == provider_id))
        assert provider is not None
        assert provider.api_key_encrypted
        assert SECRET not in provider.api_key_encrypted
        # Fernet tokens are decryptable but not readable as plaintext
        assert provider.api_key_encrypted.startswith("gAAAA")


async def test_patch_without_key_keeps_existing_key(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    created = await client.post(
        "/api/v1/providers",
        json={
            "name": "Keep Key",
            "kind": "openai_compatible",
            "base_url": "https://api.example.com/v1",
            "api_key": SECRET,
        },
        headers=auth_headers,
    )
    provider_id = created.json()["id"]
    patched = await client.patch(
        f"/api/v1/providers/{provider_id}", json={"name": "Renamed"}, headers=auth_headers
    )
    assert patched.status_code == 200
    assert patched.json()["has_api_key"] is True
    assert SECRET not in patched.text

    cleared = await client.patch(
        f"/api/v1/providers/{provider_id}", json={"api_key": ""}, headers=auth_headers
    )
    assert cleared.status_code == 200
    assert cleared.json()["has_api_key"] is False


async def test_provider_connection_check_reports_failure(
    client: httpx.AsyncClient, auth_headers: dict[str, str], mock_llm
) -> None:
    created = await client.post(
        "/api/v1/providers",
        json={"name": "Broken", "kind": "ollama", "base_url": "http://mock:11434"},
        headers=auth_headers,
    )
    provider_id = created.json()["id"]
    mock_llm["handler"] = lambda request: httpx.Response(500, content=b"boom")

    checked = await client.post(
        f"/api/v1/providers/{provider_id}/test-connection", headers=auth_headers
    )
    assert checked.status_code == 200
    assert checked.json()["status"] == "error"

    detail = await client.get(f"/api/v1/providers/{provider_id}", headers=auth_headers)
    assert detail.json()["last_check_status"] == "error"


async def test_provider_connection_check_lists_models(
    client: httpx.AsyncClient, auth_headers: dict[str, str], mock_llm
) -> None:
    created = await client.post(
        "/api/v1/providers",
        json={"name": "Healthy", "kind": "ollama", "base_url": "http://mock:11434"},
        headers=auth_headers,
    )
    provider_id = created.json()["id"]
    mock_llm["handler"] = lambda request: httpx.Response(
        200, json={"models": [{"name": "llama3.2:3b"}, {"name": "bge-m3:latest"}]}
    )

    checked = await client.post(
        f"/api/v1/providers/{provider_id}/test-connection", headers=auth_headers
    )
    assert checked.status_code == 200
    payload = checked.json()
    assert payload["status"] == "ok"
    assert payload["models"] == ["bge-m3:latest", "llama3.2:3b"]

    detail = await client.get(f"/api/v1/providers/{provider_id}", headers=auth_headers)
    assert detail.json()["last_check_status"] == "ok"
    assert detail.json()["models_cache"] == ["bge-m3:latest", "llama3.2:3b"]
