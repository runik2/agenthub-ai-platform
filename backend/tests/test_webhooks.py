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
    valid_invalid_body_signature = (
        "sha256=" + hmac.new(secret.encode(), invalid_body, hashlib.sha256).hexdigest()
    )
    invalid_body_response = await client.post(
        "/api/v1/webhooks/incoming/approval-orders",
        content=invalid_body,
        headers={"X-AgentHub-Signature": valid_invalid_body_signature},
    )
    assert invalid_body_response.status_code == 400


async def test_failed_webhook_delivery_can_be_retried(
    client: httpx.AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    class FailingQueue:
        async def enqueue(self, *_args, **_kwargs) -> None:
            raise RuntimeError("redis unavailable")

    workflow = await client.post(
        "/api/v1/workflows",
        json={"name": "Retry workflow", "description": "", "enabled": True, "steps": []},
        headers=auth_headers,
    )
    created = await client.post(
        "/api/v1/webhooks/endpoints",
        json={"name": "Retry orders", "slug": "retry-orders", "workflow_id": workflow.json()["id"]},
        headers=auth_headers,
    )
    endpoint = created.json()
    body = b'{"order_id":"99"}'
    signature = "sha256=" + hmac.new(endpoint["secret"].encode(), body, hashlib.sha256).hexdigest()
    monkeypatch.setattr(webhooks, "get_queue", lambda: FailingQueue())
    failed = await client.post(
        "/api/v1/webhooks/incoming/retry-orders",
        content=body,
        headers={"X-AgentHub-Signature": signature},
    )
    assert failed.status_code == 503
    deliveries = await client.get(
        f"/api/v1/webhooks/endpoints/{endpoint['id']}/deliveries", headers=auth_headers
    )
    delivery = deliveries.json()[0]
    assert delivery["status"] == "failed"

    class WorkingQueue:
        async def enqueue(self, *_args, **_kwargs) -> None:
            return None

    monkeypatch.setattr(webhooks, "get_queue", lambda: WorkingQueue())
    retried = await client.post(
        f"/api/v1/webhooks/endpoints/{endpoint['id']}/deliveries/{delivery['id']}/retry",
        headers=auth_headers,
    )
    assert retried.status_code == 200, retried.text
    assert retried.json()["status"] == "retrying"


async def test_webhook_event_id_is_idempotent(
    client: httpx.AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    class FakeQueue:
        def __init__(self) -> None:
            self.calls = 0

        async def enqueue(self, *_args, **_kwargs) -> None:
            self.calls += 1

    queue = FakeQueue()
    monkeypatch.setattr(webhooks, "get_queue", lambda: queue)
    workflow = await client.post(
        "/api/v1/workflows",
        json={"name": "Idempotent workflow", "description": "", "enabled": True, "steps": []},
        headers=auth_headers,
    )
    endpoint_response = await client.post(
        "/api/v1/webhooks/endpoints",
        json={"name": "Idempotent", "slug": "idempotent", "workflow_id": workflow.json()["id"]},
        headers=auth_headers,
    )
    endpoint = endpoint_response.json()
    body = b'{"event":"created"}'
    signature = "sha256=" + hmac.new(endpoint["secret"].encode(), body, hashlib.sha256).hexdigest()
    headers = {"X-AgentHub-Signature": signature, "X-AgentHub-Event-ID": "evt-42"}
    first = await client.post("/api/v1/webhooks/incoming/idempotent", content=body, headers=headers)
    second = await client.post("/api/v1/webhooks/incoming/idempotent", content=body, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"
    assert queue.calls == 1


async def test_viewer_cannot_configure_webhook_endpoint(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    workflow = await client.post(
        "/api/v1/workflows",
        json={"name": "Viewer webhook workflow", "description": "", "enabled": True, "steps": []},
        headers=auth_headers,
    )
    member = await client.post(
        "/api/v1/team",
        json={
            "email": "webhook-viewer@example.com",
            "full_name": "Webhook Viewer",
            "password": "viewer123",
            "role": "viewer",
        },
        headers=auth_headers,
    )
    login = await client.post(
        "/api/v1/auth/login", json={"email": member.json()["email"], "password": "viewer123"}
    )
    viewer_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = await client.post(
        "/api/v1/webhooks/endpoints",
        json={"name": "Viewer endpoint", "slug": "viewer-endpoint", "workflow_id": workflow.json()["id"]},
        headers=viewer_headers,
    )
    assert response.status_code == 403
