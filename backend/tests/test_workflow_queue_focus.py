from __future__ import annotations

import json

import pytest

from app.queue.arq import ArqTaskQueue
from app.schemas.tasks import Step
from app.services.workflows import execute_workflow


@pytest.mark.asyncio
async def test_workflow_condition_and_safe_tools() -> None:
    workflow = type("WorkflowStub", (), {"steps": [
        Step(id="skip", tool="text_template", template="bad", condition="missing").model_dump(),
        Step(id="json", tool="json_extract", path="answer").model_dump(),
    ]})()
    result = await execute_workflow(None, workflow, '{"answer":"ok"}')
    assert result == "ok"


@pytest.mark.asyncio
async def test_workflow_condition_routes_to_named_branch() -> None:
    workflow = type(
        "WorkflowStub",
        (),
        {
            "owner_id": "owner",
            "steps": [
                {
                    "type": "condition",
                    "condition": {"type": "if_contains", "value": "approved"},
                    "on_true": "approved",
                    "on_false": "rejected",
                },
                {"type": "tool", "tool": "text_template", "template": "YES: {input}", "branch": "approved"},
                {"type": "tool", "tool": "text_template", "template": "NO: {input}", "branch": "rejected"},
            ],
        },
    )()
    result = await execute_workflow(None, workflow, "approved order")
    assert result == "YES: approved order"


@pytest.mark.asyncio
async def test_workflow_parallel_branches_join_results() -> None:
    workflow = type(
        "WorkflowStub",
        (),
        {
            "owner_id": "owner",
            "id": "parallel-workflow",
            "steps": [
                {
                    "type": "parallel",
                    "branches": [
                        {
                            "name": "sales",
                            "steps": [
                                {"type": "tool", "tool": "text_template", "template": "sales: {input}"}
                            ],
                        },
                        {
                            "name": "support",
                            "steps": [
                                {"type": "tool", "tool": "text_template", "template": "support: {input}"}
                            ],
                        },
                    ],
                }
            ],
        },
    )()
    result = await execute_workflow(None, workflow, "lead")
    assert json.loads(result) == {"sales": "sales: lead", "support": "support: lead"}


@pytest.mark.asyncio
async def test_workflow_trace_records_step_io_and_duration() -> None:
    workflow = type(
        "WorkflowStub",
        (),
        {
            "owner_id": "owner",
            "id": "trace-workflow",
            "steps": [
                {"type": "tool", "tool": "text_template", "template": "done: {input}"}
            ],
        },
    )()
    trace: list[dict] = []
    result = await execute_workflow(None, workflow, "input", trace)
    assert result == "done: input"
    assert trace[0]["input"] == "input"
    assert trace[0]["output"] == "done: input"
    assert trace[0]["duration_ms"] >= 0
    assert trace[0]["error"] is None


def test_arq_queue_lifecycle_is_local_import_safe() -> None:
    queue = ArqTaskQueue("redis://localhost:6379/0")
    queue.start()
    assert queue.name == "arq+redis"


@pytest.mark.asyncio
async def test_worker_ping() -> None:
    from app.worker import ping

    assert await ping() == "pong"


@pytest.mark.asyncio
async def test_analytics_export(client, auth_headers) -> None:
    response = await client.get("/api/v1/analytics/export?format=csv", headers=auth_headers)
    assert response.status_code == 200
    assert "tasks,workflows,schedules,task_runs,days" in response.text


@pytest.mark.asyncio
async def test_workflow_performance_analytics(client, auth_headers) -> None:
    response = await client.get("/api/v1/analytics/workflow-performance", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert {"days", "totals", "steps"} <= payload.keys()
    assert {"runs", "steps", "failed_steps", "avg_duration_ms", "p95_duration_ms"} <= payload["totals"].keys()


@pytest.mark.asyncio
async def test_economics_includes_workflow_breakdown(client, auth_headers) -> None:
    response = await client.get("/api/v1/analytics/economics", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["workflows"], list)
    assert isinstance(payload["users"], list)
