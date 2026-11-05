from __future__ import annotations

import asyncio
import json
import time

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.metrics import metrics
from app.db.models import Agent, IntegrationTool, LLMProvider
from app.services import llm


async def _call_integration(method: str, url: str, content: str, step: dict) -> str:
    """Call an allowlisted integration with bounded timeout and retries."""
    retries = min(max(int(step.get("retries", 0) or 0), 0), 3)
    timeout_seconds = min(max(float(step.get("timeout_seconds", 15) or 15), 1), 120)
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=False) as client:
                response = await client.request(method, url, content=content)
            if response.status_code >= 400:
                raise ValueError(f"integration returned HTTP {response.status_code}")
            return response.text[:20_000]
        except (httpx.HTTPError, ValueError) as exc:
            last_error = exc
            if attempt < retries:
                await asyncio.sleep(min(0.25 * (2**attempt), 2))
    raise last_error or ValueError("integration request failed")


async def _execute_steps(
    session: AsyncSession | None,
    owner_id: str,
    workflow_id: str,
    steps: list[dict],
    initial: str,
    trace: list[dict] | None = None,
) -> str:
    value = initial
    active_branch: str | None = None
    for step in steps or []:
        step_type = step.get("type", "agent")
        step_input = value
        started = time.perf_counter()
        try:
            if step_type == "condition":
                condition = step.get("condition") or {}
                if isinstance(condition, str):
                    condition = {"type": "if_contains", "value": condition}
                expected = str(condition.get("value", ""))
                matches = (
                    expected in value
                    if condition.get("type", "if_contains") == "if_contains"
                    else expected not in value
                )
                active_branch = step.get("on_true", "true") if matches else step.get("on_false", "false")
                continue
            if step.get("branch") and step.get("branch") != active_branch:
                continue
            if step_type == "approval":
                continue
            if step_type == "parallel":
                branches = step.get("branches") or []
                branch_input = value

                async def run_branch(branch: dict, branch_input: str = branch_input) -> tuple[str, str]:
                    if session is None:
                        branch_result = await _execute_steps(
                            None, owner_id, workflow_id, branch.get("steps", []), branch_input
                        )
                    else:
                        from app.db.session import get_session_factory

                        async with get_session_factory()() as branch_session:
                            branch_result = await _execute_steps(
                                branch_session,
                                owner_id,
                                workflow_id,
                                branch.get("steps", []),
                                branch_input,
                            )
                    return str(branch.get("name") or f"branch_{len(branch.get('steps', []))}"), branch_result

                branch_results = await asyncio.gather(*(run_branch(branch) for branch in branches))
                value = json.dumps(dict(branch_results), ensure_ascii=False)
                continue
            condition = step.get("condition") or {}
            if isinstance(condition, str):
                condition = {"type": "if_contains", "value": condition}
            if condition.get("type") == "if_contains" and condition.get("value", "") not in value:
                continue
            tool = step.get("tool")
            if tool:
                if tool == "text_template":
                    value = step.get("template", "{input}").replace("{input}", value)
                elif tool == "json_extract":
                    value = str(json.loads(value).get(step.get("path", ""), ""))
                elif tool == "http_get":
                    raise ValueError("http_get is deprecated; register an allowlisted integration tool")
                else:
                    if session is None:
                        raise AppError("TOOL_NOT_FOUND", "Workflow tool requires a database session", 404)
                    tool_config = await session.get(IntegrationTool, step.get("tool_id"))
                    if not tool_config or tool_config.owner_id != owner_id:
                        raise AppError("TOOL_NOT_FOUND", "Workflow tool is not owned by workflow owner", 404)
                    if not tool_config.is_active:
                        raise AppError("TOOL_INACTIVE", "Workflow tool is disabled", 409)
                    url = f"{tool_config.base_url.rstrip('/')}/{tool_config.allowed_path.lstrip('/')}"
                    value = await _call_integration(tool_config.method, url, value, step)
                continue
            if session is None:
                value = step.get("prompt", "{input}").replace("{input}", value)
                continue
            agent = await session.get(Agent, step.get("agent_id")) if step.get("agent_id") else None
            if step.get("agent_id") and (not agent or agent.owner_id != owner_id):
                raise AppError("FORBIDDEN", "Workflow step agent is not owned by workflow owner", 403)
            if not agent or not agent.provider_id:
                value = step.get("prompt", "{input}").replace("{input}", value)
                continue
            provider = await session.get(LLMProvider, agent.provider_id)
            answer = await llm.chat(
                provider,
                agent.model_name or provider.default_model,
                [
                    {"role": "system", "content": agent.system_prompt},
                    {"role": "user", "content": step.get("prompt", "{input}").replace("{input}", value)},
                ],
                agent.temperature,
                agent.max_tokens,
            )
            value = answer.content
        finally:
            if trace is not None:
                trace.append(
                    {
                        "step_id": step.get("id"),
                        "type": step_type,
                        "input": step_input,
                        "output": value,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    }
                )
            metrics.observe_workflow_step(
                workflow_id, step_type, round((time.perf_counter() - started) * 1000, 2)
            )
    return value


async def execute_workflow(
    session: AsyncSession, workflow, initial: str, trace: list[dict] | None = None
) -> str:
    return await _execute_steps(
        session,
        getattr(workflow, "owner_id", "unknown"),
        getattr(workflow, "id", "unknown"),
        workflow.steps or [],
        initial,
        trace,
    )
