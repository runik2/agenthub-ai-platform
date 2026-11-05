from __future__ import annotations

import httpx


async def test_approval_can_edit_input_before_one_time_run(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    workflow = await client.post(
        "/api/v1/workflows",
        json={
            "name": "Approval workflow",
            "description": "",
            "enabled": True,
            "steps": [{"id": "approval", "type": "approval"}],
        },
        headers=auth_headers,
    )
    assert workflow.status_code == 201, workflow.text
    task = await client.post(
        "/api/v1/tasks",
        json={"name": "Review request", "input": "unsafe draft", "workflow_id": workflow.json()["id"]},
        headers=auth_headers,
    )
    assert task.status_code == 201, task.text
    assert task.json()["status"] == "waiting_approval"
    edited = await client.post(
        f"/api/v1/tasks/{task.json()['id']}/approve-and-run",
        json={"input": "approved and edited"},
        headers=auth_headers,
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["input"] == "approved and edited"
    assert edited.json()["approved_at"] is not None


async def test_workflow_versions_can_restore_previous_configuration(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    created = await client.post(
        "/api/v1/workflows",
        json={"name": "Versioned flow", "description": "v1", "enabled": True, "steps": []},
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text
    workflow_id = created.json()["id"]
    updated = await client.put(
        f"/api/v1/workflows/{workflow_id}",
        json={"name": "Versioned flow", "description": "v2", "enabled": True, "steps": []},
        headers=auth_headers,
    )
    assert updated.status_code == 200, updated.text
    versions = await client.get(f"/api/v1/workflows/{workflow_id}/versions", headers=auth_headers)
    assert versions.status_code == 200, versions.text
    assert [item["version"] for item in versions.json()[:2]] == [2, 1]
    restored = await client.post(
        f"/api/v1/workflows/{workflow_id}/versions/{versions.json()[1]['id']}/restore",
        json={"note": "Back to stable"},
        headers=auth_headers,
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["description"] == "v1"
    latest = await client.get(f"/api/v1/workflows/{workflow_id}/versions", headers=auth_headers)
    assert latest.json()[0]["version"] == 3
    assert latest.json()[0]["note"] == "Back to stable"
