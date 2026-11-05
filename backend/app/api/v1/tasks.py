from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import Agent, IntegrationTool, Task, TaskRun, User, Workflow
from app.db.session import get_session
from app.queue.runtime import get_queue
from app.schemas.tasks import TaskCreate, TaskOut

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskOut])
async def list_tasks(
    status: str | None = Query(None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    q = select(Task).where(Task.owner_id == user.id).order_by(Task.created_at.desc())
    if status:
        q = q.where(Task.status == status)
    return list((await session.scalars(q)).all())


@router.post("", response_model=TaskOut, status_code=201)
async def create_task(
    payload: TaskCreate, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    values = payload.model_dump()
    if values["agent_id"] and not await session.scalar(
        select(Agent.id).where(Agent.id == values["agent_id"], Agent.owner_id == user.id)
    ):
        from app.core.errors import AppError

        raise AppError("NOT_FOUND", "Agent not found", 404)
    if values["workflow_id"] and not await session.scalar(
        select(Workflow.id).where(Workflow.id == values["workflow_id"], Workflow.owner_id == user.id)
    ):
        from app.core.errors import AppError

        raise AppError("NOT_FOUND", "Workflow not found", 404)
    workflow_requires_approval = False
    if values["workflow_id"]:
        workflow = await session.get(Workflow, values["workflow_id"])
        workflow_requires_approval = bool(
            workflow and any(step.get("type") == "approval" for step in workflow.steps or [])
        )
        if workflow and not workflow_requires_approval:
            tool_ids = [step.get("tool_id") for step in workflow.steps or [] if step.get("tool_id")]
            if tool_ids:
                workflow_requires_approval = bool(
                    await session.scalar(
                        select(IntegrationTool.id).where(
                            IntegrationTool.id.in_(tool_ids),
                            IntegrationTool.owner_id == user.id,
                            IntegrationTool.requires_approval.is_(True),
                        )
                    )
                )
    task = Task(owner_id=user.id, requires_approval=workflow_requires_approval, **values)
    if workflow_requires_approval:
        task.status = "waiting_approval"
    session.add(task)
    await session.commit()
    await session.refresh(task)
    try:
        if task.status == "waiting_approval":
            return task
        await get_queue().enqueue("execute_task", {"task_id": task.id})
    except Exception as exc:
        task.status, task.error = "failed", f"queue enqueue failed: {exc}"
        await session.commit()
    return task


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(
    task_id: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    task = await session.scalar(select(Task).where(Task.id == task_id, Task.owner_id == user.id))
    if not task:
        from app.core.errors import AppError

        raise AppError("NOT_FOUND", "Task not found", 404)
    return task


@router.post("/{task_id}/run", response_model=TaskOut)
async def run_task(
    task_id: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    task = await session.scalar(select(Task).where(Task.id == task_id, Task.owner_id == user.id))
    if not task:
        from app.core.errors import AppError

        raise AppError("NOT_FOUND", "Task not found", 404)
    task.status = "waiting_approval" if task.requires_approval and task.approved_at is None else "pending"
    await session.commit()
    try:
        if task.status == "waiting_approval":
            await session.commit()
            await session.refresh(task)
            return task
        await get_queue().enqueue("execute_task", {"task_id": task.id})
    except Exception as exc:
        task.status, task.error = "failed", f"queue enqueue failed: {exc}"
        await session.commit()
    await session.refresh(task)
    return task


@router.post("/{task_id}/approve", response_model=TaskOut)
async def approve_task(
    task_id: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    task = await session.scalar(select(Task).where(Task.id == task_id, Task.owner_id == user.id))
    if not task:
        from app.core.errors import AppError

        raise AppError("NOT_FOUND", "Task not found", 404)
    if task.status != "waiting_approval":
        from app.core.errors import AppError

        raise AppError("APPROVAL_NOT_PENDING", "Task is not waiting for approval", 409)
    task.status, task.approved_at, task.approved_by_id = "pending", datetime.now(UTC), user.id
    await session.commit()
    try:
        await get_queue().enqueue("execute_task", {"task_id": task.id})
    except Exception as exc:
        task.status, task.error = "failed", f"queue enqueue failed: {exc}"
        await session.commit()
    await session.refresh(task)
    return task


@router.post("/{task_id}/reject", response_model=TaskOut)
async def reject_task(
    task_id: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    task = await session.scalar(select(Task).where(Task.id == task_id, Task.owner_id == user.id))
    if not task:
        from app.core.errors import AppError

        raise AppError("NOT_FOUND", "Task not found", 404)
    if task.status != "waiting_approval":
        from app.core.errors import AppError

        raise AppError("APPROVAL_NOT_PENDING", "Task is not waiting for approval", 409)
    task.status, task.error = "rejected", "Rejected by operator"
    await session.commit()
    await session.refresh(task)
    return task


@router.get("/{task_id}/runs")
async def task_runs(
    task_id: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    allowed = await session.scalar(select(Task.id).where(Task.id == task_id, Task.owner_id == user.id))
    if not allowed:
        from app.core.errors import AppError

        raise AppError("NOT_FOUND", "Task not found", 404)
    return list(
        (
            await session.scalars(
                select(TaskRun).where(TaskRun.task_id == task_id).order_by(TaskRun.created_at.desc())
            )
        ).all()
    )
