from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles, workspace_owner_id
from app.db.models import User, Workflow, WorkflowVersion
from app.db.session import get_session
from app.queue.runtime import get_queue
from app.schemas.tasks import WorkflowCreate, WorkflowOut, WorkflowRestore, WorkflowVersionOut

router = APIRouter(prefix="/workflows", tags=["workflows"])


async def snapshot_workflow(
    session: AsyncSession,
    workflow: Workflow,
    user_id: str | None,
    note: str = "",
) -> WorkflowVersion:
    latest = await session.scalar(
        select(func.max(WorkflowVersion.version)).where(WorkflowVersion.workflow_id == workflow.id)
    )
    version = WorkflowVersion(
        owner_id=workflow.owner_id,
        workflow_id=workflow.id,
        version=(latest or 0) + 1,
        name=workflow.name,
        description=workflow.description,
        enabled=workflow.enabled,
        steps=workflow.steps,
        note=note,
        created_by=user_id,
    )
    session.add(version)
    return version


@router.get("", response_model=list[WorkflowOut])
async def list_workflows(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    return list(
        (
            await session.scalars(
                select(Workflow)
                .where(Workflow.owner_id == workspace_owner_id(user))
                .order_by(Workflow.created_at.desc())
            )
        ).all()
    )


@router.post("", response_model=WorkflowOut, status_code=201)
async def create_workflow(
    payload: WorkflowCreate,
    user: User = Depends(require_roles("admin", "manager")),
    session: AsyncSession = Depends(get_session),
):
    wf = Workflow(owner_id=workspace_owner_id(user), **payload.model_dump())
    session.add(wf)
    await session.flush()
    await snapshot_workflow(session, wf, user.id, "Initial workflow version")
    await session.commit()
    await session.refresh(wf)
    return wf


@router.get("/{workflow_id}", response_model=WorkflowOut)
async def get_workflow(
    workflow_id: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    workflow = await session.scalar(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.owner_id == workspace_owner_id(user))
    )
    if not workflow:
        from app.core.errors import AppError

        raise AppError("NOT_FOUND", "Workflow not found", 404)
    return workflow


@router.put("/{workflow_id}", response_model=WorkflowOut)
async def update_workflow(
    workflow_id: str,
    payload: WorkflowCreate,
    user: User = Depends(require_roles("admin", "manager")),
    session: AsyncSession = Depends(get_session),
):
    wf = await session.scalar(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.owner_id == workspace_owner_id(user))
    )
    if not wf:
        from app.core.errors import AppError

        raise AppError("NOT_FOUND", "Workflow not found", 404)
    for key, value in payload.model_dump().items():
        setattr(wf, key, value)
    await session.flush()
    await snapshot_workflow(session, wf, user.id, "Workflow updated")
    await session.commit()
    await session.refresh(wf)
    return wf


@router.get("/{workflow_id}/versions", response_model=list[WorkflowVersionOut])
async def list_workflow_versions(
    workflow_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[WorkflowVersionOut]:
    owner_id = workspace_owner_id(user)
    workflow = await session.scalar(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.owner_id == owner_id)
    )
    if not workflow:
        from app.core.errors import AppError

        raise AppError("NOT_FOUND", "Workflow not found", 404)
    return list(
        (
            await session.scalars(
                select(WorkflowVersion)
                .where(WorkflowVersion.workflow_id == workflow_id, WorkflowVersion.owner_id == owner_id)
                .order_by(WorkflowVersion.version.desc())
            )
        ).all()
    )


@router.post("/{workflow_id}/versions/{version_id}/restore", response_model=WorkflowOut)
async def restore_workflow_version(
    workflow_id: str,
    version_id: str,
    payload: WorkflowRestore = WorkflowRestore(),
    user: User = Depends(require_roles("admin", "manager")),
    session: AsyncSession = Depends(get_session),
) -> WorkflowOut:
    owner_id = workspace_owner_id(user)
    workflow = await session.scalar(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.owner_id == owner_id)
    )
    version = await session.scalar(
        select(WorkflowVersion).where(
            WorkflowVersion.id == version_id,
            WorkflowVersion.workflow_id == workflow_id,
            WorkflowVersion.owner_id == owner_id,
        )
    )
    if not workflow or not version:
        from app.core.errors import AppError

        raise AppError("WORKFLOW_VERSION_NOT_FOUND", "Workflow version not found", 404)
    workflow.name = version.name
    workflow.description = version.description
    workflow.enabled = version.enabled
    workflow.steps = version.steps
    await session.flush()
    await snapshot_workflow(session, workflow, user.id, payload.note)
    await session.commit()
    await session.refresh(workflow)
    return workflow


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(
    workflow_id: str,
    user: User = Depends(require_roles("admin", "manager")),
    session: AsyncSession = Depends(get_session),
):
    wf = await session.scalar(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.owner_id == workspace_owner_id(user))
    )
    if not wf:
        from app.core.errors import AppError

        raise AppError("NOT_FOUND", "Workflow not found", 404)
    await session.delete(wf)
    await session.commit()


@router.post("/{workflow_id}/run", status_code=202)
async def run_workflow(
    workflow_id: str,
    user: User = Depends(require_roles("admin", "manager", "operator")),
    session: AsyncSession = Depends(get_session),
):
    wf = await session.scalar(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.owner_id == workspace_owner_id(user))
    )
    if not wf:
        from app.core.errors import AppError

        raise AppError("NOT_FOUND", "Workflow not found", 404)
    from app.db.models import Task

    task = Task(owner_id=workspace_owner_id(user), workflow_id=wf.id, name=f"Workflow: {wf.name}", input="")
    session.add(task)
    await session.commit()
    await session.refresh(task)
    try:
        await get_queue().enqueue("execute_task", {"task_id": task.id})
    except Exception as exc:
        task.status, task.error = "failed", f"queue enqueue failed: {exc}"
        await session.commit()
    return {"task_id": task.id}
