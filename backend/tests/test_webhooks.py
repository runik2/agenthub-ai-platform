from __future__ import annotations

import hashlib
import hmac

import httpx

from app.api.v1 import webhooks


async def test_signed_webhook_queues_workflow_and_rejects_bad_signature(
    client: httpx.AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    class FakeQueue:
        async def enqueue(self, *_args, **_kwargs) -> None:
            return None

    monkeypatch.setattr(webhooks, "get_queue", lambda: FakeQueue())
    workflow = await client.post(
        "/api/v1/workflows",
        json={"name": "Incoming order", "description": "", "enabled": True, "steps": []},
        headers=auth_headers,
    )
    assert workflow.status_code == 201, workflow.text
    created = await client.post(
        "/api/v1/webhooks/endpoints",
        json={"name": "Orders", "slug": "orders", "workflow_id": workflow.json()["id"]},
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text
    secret = created.json()["secret"]
    body = b'{"order_id":"42"}'
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    accepted = await client.post(
        "/api/v1/webhooks/incoming/orders",
        content=body,
        headers={"X-AgentHub-Signature": signature},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "accepted"
    rejected = await client.post(
        "/api/v1/webhooks/incoming/orders",
        content=body,
        headers={"X-AgentHub-Signature": "sha256=bad"},
    )
    assert rejected.status_code == 401
