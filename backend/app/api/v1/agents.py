from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, write_audit
from app.core.errors import AppError
from app.core.pagination import Pagination, paginate
from app.db.models import Agent, Conversation, PromptVersion, User
from app.db.session import get_session
from app.schemas.agents import AgentCreate, AgentOut, AgentTemplate, AgentUpdate
from app.schemas.common import Page, StatusResponse
from app.schemas.prompt_versions import PromptRollback, PromptVersionOut
from app.services.agent_templates import TEMPLATES, get_template

router = APIRouter(prefix="/agents", tags=["agents"])


def slugify(value: str) -> str:
    cleaned = []
    previous_dash = False
    for char in value.lower():
        if char.isascii() and char.isalnum():
            cleaned.append(char)
            previous_dash = False
        elif not previous_dash:
            cleaned.append("-")
            previous_dash = True
    slug = "".join(cleaned).strip("-")
    return slug or "agent"


async def unique_slug(session: AsyncSession, name: str, ignore_id: str | None = None) -> str:
    base = slugify(name)
    candidate = base
    counter = 2
    while True:
        stmt = select(Agent.id).where(Agent.slug == candidate)
        if ignore_id:
            stmt = stmt.where(Agent.id != ignore_id)
        if await session.scalar(stmt) is None:
            return candidate
        candidate = f"{base}-{counter}"
        counter += 1


async def get_owned_agent(session: AsyncSession, user: User, agent_id: str) -> Agent:
    agent = await session.scalar(select(Agent).where(Agent.id == agent_id, Agent.owner_id == user.id))
    if agent is None:
        raise AppError("AGENT_NOT_FOUND", "Agent not found", 404)
    return agent


async def snapshot_prompt(session: AsyncSession, agent: Agent, note: str) -> PromptVersion:
    latest = await session.scalar(
        select(func.max(PromptVersion.version)).where(PromptVersion.agent_id == agent.id)
    )
    snapshot = PromptVersion(
        owner_id=agent.owner_id,
        agent_id=agent.id,
        version=(latest or 0) + 1,
        system_prompt=agent.system_prompt,
        note=note,
    )
    session.add(snapshot)
    return snapshot


@router.get("/templates", response_model=list[AgentTemplate])
async def list_templates() -> list[AgentTemplate]:
    return TEMPLATES


@router.get("", response_model=Page[AgentOut])
async def list_agents(
    pagination: Pagination = Depends(),
    search: str = Query(default="", max_length=120),
    status: str = Query(default="", max_length=20),
    tag: str = Query(default="", max_length=40),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Page[AgentOut]:
    stmt = select(Agent).where(Agent.owner_id == user.id)
    if search.strip():
        pattern = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                Agent.name.ilike(pattern),
                Agent.description.ilike(pattern),
                Agent.slug.ilike(pattern),
            )
        )
    if status.strip():
        stmt = stmt.where(Agent.status == status.strip())
    stmt = stmt.order_by(Agent.created_at.desc())
    rows, total, pages = await paginate(session, stmt, pagination)
    if tag.strip():
        rows = [row for row in rows if tag.strip() in (row.tags or [])]
    return Page[AgentOut](
        items=[AgentOut.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        pages=pages,
    )


@router.post("", response_model=AgentOut, status_code=201)
async def create_agent(
    payload: AgentCreate,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AgentOut:
    agent = Agent(
        **payload.model_dump(),
        slug=await unique_slug(session, payload.name),
        owner_id=user.id,
    )
    session.add(agent)
    await session.flush()
    await snapshot_prompt(session, agent, "Initial prompt")
    await write_audit(session, request, user.id, "agent.created", "agent", agent.id, {"name": agent.name})
    await session.commit()
    await session.refresh(agent)
    return AgentOut.model_validate(agent)


@router.post("/from-template/{template_slug}", response_model=AgentOut, status_code=201)
async def create_from_template(
    template_slug: str,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AgentOut:
    template = get_template(template_slug)
    if template is None:
        raise AppError("TEMPLATE_NOT_FOUND", "Unknown agent template", 404)
    agent = Agent(
        name=template.name,
        slug=await unique_slug(session, template.name),
        description=template.description,
        system_prompt=template.system_prompt,
        greeting=template.greeting,
        model_name=template.model_name,
        temperature=template.temperature,
        max_tokens=template.max_tokens,
        status="draft",
        avatar_color=template.avatar_color,
        tags=list(template.tags),
        template_slug=template.slug,
        owner_id=user.id,
    )
    session.add(agent)
    await session.flush()
    await snapshot_prompt(session, agent, "Created from template")
    await write_audit(
        session,
        request,
        user.id,
        "agent.created_from_template",
        "agent",
        agent.id,
        {"template": template.slug},
    )
    await session.commit()
    await session.refresh(agent)
    return AgentOut.model_validate(agent)


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(
    agent_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AgentOut:
    agent = await get_owned_agent(session, user, agent_id)
    return AgentOut.model_validate(agent)


@router.patch("/{agent_id}", response_model=AgentOut)
async def update_agent(
    agent_id: str,
    payload: AgentUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AgentOut:
    agent = await get_owned_agent(session, user, agent_id)
    data = payload.model_dump(exclude_unset=True)
    if "provider_id" in data and data["provider_id"] is not None:
        from app.db.models import LLMProvider

        if await session.get(LLMProvider, data["provider_id"]) is None:
            raise AppError("PROVIDER_NOT_FOUND", "Provider not found", 404)
    if "name" in data and data["name"] != agent.name:
        agent.slug = await unique_slug(session, data["name"], ignore_id=agent.id)
    if "tags" in data and data["tags"] is not None:
        data["tags"] = list(dict.fromkeys(tag.strip()[:32] for tag in data["tags"] if tag.strip()))[:12]
    for field, value in data.items():
        setattr(agent, field, value)
    if "system_prompt" in data:
        await snapshot_prompt(session, agent, "Prompt updated")
    await write_audit(session, request, user.id, "agent.updated", "agent", agent.id)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError("AGENT_CONFLICT", "Agent could not be saved", 409) from exc
    await session.refresh(agent)
    return AgentOut.model_validate(agent)


@router.get("/{agent_id}/prompt-versions", response_model=list[PromptVersionOut])
async def list_prompt_versions(
    agent_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[PromptVersionOut]:
    await get_owned_agent(session, user, agent_id)
    rows = await session.scalars(
        select(PromptVersion)
        .where(PromptVersion.agent_id == agent_id, PromptVersion.owner_id == user.id)
        .order_by(PromptVersion.version.desc())
    )
    return [PromptVersionOut.model_validate(row) for row in rows]


@router.post("/{agent_id}/prompt-versions/{version_id}/restore", response_model=AgentOut)
async def restore_prompt_version(
    agent_id: str,
    version_id: str,
    request: Request,
    payload: PromptRollback = PromptRollback(),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AgentOut:
    agent = await get_owned_agent(session, user, agent_id)
    version = await session.scalar(
        select(PromptVersion).where(
            PromptVersion.id == version_id,
            PromptVersion.agent_id == agent.id,
            PromptVersion.owner_id == user.id,
        )
    )
    if not version:
        raise AppError("PROMPT_VERSION_NOT_FOUND", "Prompt version not found", 404)
    agent.system_prompt = version.system_prompt
    await snapshot_prompt(session, agent, payload.note or f"Restored version {version.version}")
    await write_audit(session, request, user.id, "agent.prompt_restored", "agent", agent.id)
    await session.commit()
    await session.refresh(agent)
    return AgentOut.model_validate(agent)


@router.post("/{agent_id}/duplicate", response_model=AgentOut, status_code=201)
async def duplicate_agent(
    agent_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AgentOut:
    source = await get_owned_agent(session, user, agent_id)
    name = f"{source.name} (copy)"
    clone = Agent(
        name=name,
        slug=await unique_slug(session, name),
        description=source.description,
        system_prompt=source.system_prompt,
        greeting=source.greeting,
        provider_id=source.provider_id,
        model_name=source.model_name,
        temperature=source.temperature,
        max_tokens=source.max_tokens,
        status="draft",
        avatar_color=source.avatar_color,
        tags=list(source.tags or []),
        template_slug=source.template_slug,
        owner_id=user.id,
    )
    session.add(clone)
    await session.flush()
    await write_audit(session, request, user.id, "agent.duplicated", "agent", clone.id, {"source": source.id})
    await session.commit()
    await session.refresh(clone)
    return AgentOut.model_validate(clone)


@router.delete("/{agent_id}", response_model=StatusResponse)
async def delete_agent(
    agent_id: str,
    request: Request,
    force: bool = Query(default=False),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> StatusResponse:
    agent = await get_owned_agent(session, user, agent_id)
    conversations = await session.scalar(
        select(Conversation.id).where(Conversation.agent_id == agent.id).limit(1)
    )
    if conversations and not force:
        raise AppError(
            "AGENT_HAS_CONVERSATIONS",
            "Agent has conversations; delete with force=true to remove them",
            409,
        )
    await session.delete(agent)
    await write_audit(session, request, user.id, "agent.deleted", "agent", agent_id)
    await session.commit()
    return StatusResponse()
