from __future__ import annotations

import json
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.models import Agent, LLMProvider, Workflow
from app.services import llm


async def execute_workflow(session: AsyncSession, workflow: Workflow, initial: str) -> str:
    value = initial
    for step in workflow.steps or []:
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
                parsed = urlparse(step.get("url", ""))
                allowed = step.get("allowlist", [])
                if parsed.scheme != "https" or parsed.hostname not in allowed:
                    raise ValueError("http_get URL is not allowlisted")
                raise ValueError("http_get requires an approved HTTP client")
            else:
                raise ValueError(f"tool is not allowed: {tool}")
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
