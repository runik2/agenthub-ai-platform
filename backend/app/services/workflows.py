from __future__ import annotations

import json

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.models import Agent, IntegrationTool, LLMProvider, Workflow
from app.services import llm


async def execute_workflow(session: AsyncSession, workflow: Workflow, initial: str) -> str:
    value = initial
    active_branch: str | None = None
    for step in workflow.steps or []:
        if step.get("type") == "condition":
            condition = step.get("condition") or {}
            if isinstance(condition, str):
                condition = {"type": "if_contains", "value": condition}
            condition_type = condition.get("type", "if_contains")
            expected = str(condition.get("value", ""))
            matches = expected in value if condition_type == "if_contains" else expected not in value
            active_branch = step.get("on_true", "true") if matches else step.get("on_false", "false")
            continue
        if step.get("branch") and step.get("branch") != active_branch:
            continue
        if step.get("type") == "approval":
            # The task was held before execution. This marker documents the safe boundary in the graph.
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
                data = json.loads(value)
                value = str(data.get(step.get("path", ""), ""))
            elif tool == "http_get":
                raise ValueError("http_get is deprecated; register an allowlisted integration tool")
            else:
                tool_config = await session.get(IntegrationTool, step.get("tool_id"))
                if not tool_config or tool_config.owner_id != workflow.owner_id:
                    raise AppError("TOOL_NOT_FOUND", "Workflow tool is not owned by workflow owner", 404)
                if not tool_config.is_active:
                    raise AppError("TOOL_INACTIVE", "Workflow tool is disabled", 409)
                url = f"{tool_config.base_url.rstrip('/')}/{tool_config.allowed_path.lstrip('/')}"
                async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
                    response = await client.request(tool_config.method, url, content=value)
                if response.status_code >= 400:
                    raise ValueError(f"integration returned HTTP {response.status_code}")
                value = response.text[:20_000]
            continue
        agent = await session.get(Agent, step.get("agent_id")) if step.get("agent_id") else None
        if step.get("agent_id") and (not agent or agent.owner_id != workflow.owner_id):
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
    return value
