from ipaddress import ip_address
from urllib.parse import urlparse

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.errors import AppError
from app.db.models import IntegrationTool, User
from app.db.session import get_session
from app.schemas.tools import ToolCreate, ToolOut, ToolUpdate

router = APIRouter(prefix="/tools", tags=["tools"])


def validate_target(base_url: str, allowed_path: str) -> None:
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise AppError("INVALID_TOOL_URL", "Tool URL must be a public HTTPS URL", 422)
    try:
        if ip_address(parsed.hostname).is_private or ip_address(parsed.hostname).is_loopback:
            raise AppError("INVALID_TOOL_URL", "Private network targets are not allowed", 422)
    except ValueError:
        pass
    if not allowed_path.startswith("/") or "//" in allowed_path or "://" in allowed_path:
        raise AppError("INVALID_TOOL_PATH", "Allowed path must be a relative path", 422)


async def owned_tool(tool_id: str, user: User, session: AsyncSession) -> IntegrationTool:
    tool = await session.scalar(
        select(IntegrationTool).where(IntegrationTool.id == tool_id, IntegrationTool.owner_id == user.id)
    )
    if not tool:
        raise AppError("TOOL_NOT_FOUND", "Tool not found", 404)
    return tool


@router.get("", response_model=list[ToolOut])
async def list_tools(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    stmt = (
        select(IntegrationTool)
        .where(IntegrationTool.owner_id == user.id)
        .order_by(IntegrationTool.created_at.desc())
    )
    return list((await session.scalars(stmt)).all())


@router.post("", response_model=ToolOut, status_code=201)
async def create_tool(
    payload: ToolCreate,
    user: User = Depends(require_roles("admin", "manager")),
    session: AsyncSession = Depends(get_session),
):
    validate_target(payload.base_url, payload.allowed_path)
    tool = IntegrationTool(owner_id=user.id, **payload.model_dump())
    session.add(tool)
    await session.commit()
    await session.refresh(tool)
    return tool


@router.patch("/{tool_id}", response_model=ToolOut)
async def update_tool(
    tool_id: str,
    payload: ToolUpdate,
    user: User = Depends(require_roles("admin", "manager")),
    session: AsyncSession = Depends(get_session),
):
    tool = await owned_tool(tool_id, user, session)
    values = payload.model_dump(exclude_unset=True)
    validate_target(values.get("base_url", tool.base_url), values.get("allowed_path", tool.allowed_path))
    for key, value in values.items():
        setattr(tool, key, value)
    await session.commit()
    await session.refresh(tool)
    return tool


@router.delete("/{tool_id}", status_code=204)
async def delete_tool(
    tool_id: str,
    user: User = Depends(require_roles("admin", "manager")),
    session: AsyncSession = Depends(get_session),
):
    await session.delete(await owned_tool(tool_id, user, session))
    await session.commit()
