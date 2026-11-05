from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles, workspace_owner_id
from app.db.models import Schedule, User, Workflow
from app.db.session import get_session
from app.schemas.tasks import ScheduleCreate, ScheduleOut

router = APIRouter(prefix="/schedules", tags=["schedules"])


@router.get("", response_model=list[ScheduleOut])
async def list_schedules(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    return list(
        (await session.scalars(select(Schedule).where(Schedule.owner_id == workspace_owner_id(user)))).all()
    )


@router.post("", response_model=ScheduleOut, status_code=201)
async def create_schedule(
    payload: ScheduleCreate,
    user: User = Depends(require_roles("admin", "manager")),
    session: AsyncSession = Depends(get_session),
):
    workflow = await session.scalar(
        select(Workflow).where(
            Workflow.id == payload.workflow_id, Workflow.owner_id == workspace_owner_id(user)
        )
    )
    if not workflow:
        from app.core.errors import AppError
        raise AppError("NOT_FOUND", "Workflow not found", 404)
    row = Schedule(owner_id=workspace_owner_id(user), **payload.model_dump())
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


@router.patch("/{schedule_id}/toggle", response_model=ScheduleOut)
async def toggle_schedule(
    schedule_id: str,
    user: User = Depends(require_roles("admin", "manager")),
    session: AsyncSession = Depends(get_session),
):
    row = await session.scalar(
        select(Schedule).where(
            Schedule.id == schedule_id, Schedule.owner_id == workspace_owner_id(user)
        )
    )
    if not row:
        from app.core.errors import AppError
        raise AppError("NOT_FOUND", "Schedule not found", 404)
    row.enabled = not row.enabled
    await session.commit()
    await session.refresh(row)
    return row
