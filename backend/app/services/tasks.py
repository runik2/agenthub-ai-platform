from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.db.models import Agent, LLMProvider, Task, TaskRun, Workflow
from app.db.session import get_session_factory
from app.services import llm


async def execute_task(task_id: str) -> None:
    factory = get_session_factory()
    async with factory() as session:
        task = await session.get(Task, task_id)
        if not task:
            return
        if task.status not in {"pending", "queued"}:
            return
        task.status = "running"
        task.attempts += 1
        run = TaskRun(task_id=task.id, status="running", attempt=task.attempts, started_at=datetime.now(UTC))
        session.add(run)
        await session.commit()
        try:
            trace: list[dict] = []
            if task.workflow_id:
                from app.services.workflows import execute_workflow

                wf = await session.get(Workflow, task.workflow_id)
                result = await execute_workflow(session, wf, task.input, trace) if wf else task.input
            elif task.agent_id:
                agent = await session.get(Agent, task.agent_id)
                if not agent or not agent.provider_id:
                    raise RuntimeError("agent has no provider")
                provider = await session.get(LLMProvider, agent.provider_id)
                if not provider or provider.owner_id != task.owner_id:
                    raise RuntimeError("agent provider is not owned by task owner")
                answer = await llm.chat(
                    provider,
                    agent.model_name or provider.default_model,
                    [
                        {"role": "system", "content": agent.system_prompt},
                        {"role": "user", "content": task.input},
                    ],
                    agent.temperature,
                    agent.max_tokens,
                )
                result = answer.content
            else:
                result = task.input
            task.status = "succeeded"
            task.result = result
            run.status = "succeeded"
            run.result = result
            run.steps = trace
        except Exception as exc:  # noqa: BLE001
            task.error = str(exc)
            run.error = str(exc)
            run.steps = trace
            if task.attempts <= task.max_retries:
                task.status = "pending"
                task.next_run_at = datetime.now(UTC) + timedelta(seconds=2 ** (task.attempts - 1))
                run.status = "retrying"
                run.finished_at = datetime.now(UTC)
                await session.commit()
                return
            task.status = "failed"
            run.status = "failed"
        run.finished_at = datetime.now(UTC)
        await session.commit()
