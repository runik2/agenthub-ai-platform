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
