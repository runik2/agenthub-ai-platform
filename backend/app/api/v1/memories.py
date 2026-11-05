from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, workspace_owner_id
from app.core.errors import AppError
from app.db.models import Agent, AgentMemory, User
from app.db.session import get_session
from app.schemas.memory import MemoryCreate, MemoryOut, MemoryUpdate

router = APIRouter(prefix="/memories", tags=["memories"])


@router.get("", response_model=list[MemoryOut])
async def list_memories(
    agent_id: str | None = None,
    search: str = Query("", max_length=200),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(AgentMemory).where(AgentMemory.owner_id == workspace_owner_id(user))
    if agent_id:
        stmt = stmt.where(or_(AgentMemory.agent_id == agent_id, AgentMemory.agent_id.is_(None)))
    if search.strip():
        stmt = stmt.where(AgentMemory.content.ilike(f"%{search.strip()}%"))
    stmt = stmt.order_by(AgentMemory.is_pinned.desc(), AgentMemory.updated_at.desc())
    return list((await session.scalars(stmt)).all())


@router.post("", response_model=MemoryOut, status_code=201)
async def create_memory(
    payload: MemoryCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    agent_exists = payload.agent_id and await session.scalar(
        select(Agent.id).where(Agent.id == payload.agent_id, Agent.owner_id == workspace_owner_id(user))
    )
    if payload.agent_id and not agent_exists:
        raise AppError("AGENT_NOT_FOUND", "Agent not found", 404)
    memory = AgentMemory(owner_id=workspace_owner_id(user), source="manual", **payload.model_dump())
    session.add(memory)
    await session.commit()
    await session.refresh(memory)
    return memory


@router.patch("/{memory_id}", response_model=MemoryOut)
async def update_memory(
    memory_id: str,
    payload: MemoryUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    memory = await session.scalar(
        select(AgentMemory).where(
            AgentMemory.id == memory_id, AgentMemory.owner_id == workspace_owner_id(user)
        )
    )
    if not memory:
        raise AppError("NOT_FOUND", "Memory not found", 404)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(memory, key, value)
    await session.commit()
    await session.refresh(memory)
    return memory


@router.delete("/{memory_id}", status_code=204)
async def forget_memory(
    memory_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    memory = await session.scalar(
        select(AgentMemory).where(
            AgentMemory.id == memory_id, AgentMemory.owner_id == workspace_owner_id(user)
        )
    )
    if not memory:
        raise AppError("NOT_FOUND", "Memory not found", 404)
    await session.delete(memory)
    await session.commit()
