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


async def test_webhook_respects_approval_steps_and_rejects_invalid_json(
    client: httpx.AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    class FakeQueue:
        def __init__(self) -> None:
            self.calls: list[tuple] = []

        async def enqueue(self, *args, **kwargs) -> None:
            self.calls.append((args, kwargs))

    queue = FakeQueue()
    monkeypatch.setattr(webhooks, "get_queue", lambda: queue)
    workflow = await client.post(
        "/api/v1/workflows",
        json={
            "name": "Approval workflow",
            "description": "",
            "enabled": True,
            "steps": [{"id": "approval-1", "type": "approval", "label": "Review"}],
        },
        headers=auth_headers,
    )
    created = await client.post(
        "/api/v1/webhooks/endpoints",
        json={"name": "Approval orders", "slug": "approval-orders", "workflow_id": workflow.json()["id"]},
        headers=auth_headers,
    )
    secret = created.json()["secret"]
    body = b'{"order_id":"7"}'
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    accepted = await client.post(
        "/api/v1/webhooks/incoming/approval-orders",
        content=body,
        headers={"X-AgentHub-Signature": signature},
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "waiting_approval"
    assert queue.calls == []

    invalid = await client.post(
        "/api/v1/webhooks/incoming/approval-orders",
        content=b"not-json",
        headers={"X-AgentHub-Signature": "sha256=invalid"},
    )
    assert invalid.status_code == 401

    invalid_body = b"not-json"
    valid_invalid_body_signature = "sha256=" + hmac.new(
        secret.encode(), invalid_body, hashlib.sha256
    ).hexdigest()
    invalid_body_response = await client.post(
        "/api/v1/webhooks/incoming/approval-orders",
        content=invalid_body,
        headers={"X-AgentHub-Signature": valid_invalid_body_signature},
    )
    assert invalid_body_response.status_code == 400
