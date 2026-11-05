import time
from ipaddress import ip_address
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles, workspace_owner_id
from app.core.errors import AppError
from app.db.models import IntegrationTool, User
from app.db.session import get_session
from app.schemas.tools import ToolCreate, ToolOut, ToolTemplateOut, ToolUpdate

router = APIRouter(prefix="/tools", tags=["tools"])

TOOL_TEMPLATES = [
    {
        "id": "telegram-bridge",
        "name": "Telegram Bot bridge",
        "description": "Отправляет сообщение через ваш HTTPS-сервис-посредник в Telegram Bot API.",
        "kind": "http",
        "method": "POST",
        "base_url": "https://your-bridge.example.com",
        "allowed_path": "/telegram/send-message",
        "requires_approval": True,
        "setup_hint": "Укажите адрес собственного bridge-сервиса. Токен бота не хранится в URL AgentHub.",
    },
    {
        "id": "gmail-bridge",
        "name": "Gmail отправка через bridge",
        "description": "Создаёт письмо или черновик через ваш OAuth-сервис-посредник для Gmail.",
        "kind": "http",
        "method": "POST",
        "base_url": "https://your-bridge.example.com",
        "allowed_path": "/gmail/create-draft",
        "requires_approval": True,
        "setup_hint": (
            "Используйте OAuth bridge с секретами вне AgentHub; "
            "для отправки оставьте approval включённым."
        ),
    },
    {
        "id": "crm-webhook",
        "name": "CRM: создать лид",
        "description": "Передаёт структурированные данные лида в CRM webhook или ваш API gateway.",
        "kind": "webhook",
        "method": "POST",
        "base_url": "https://crm.example.com",
        "allowed_path": "/api/v1/leads",
        "requires_approval": True,
        "setup_hint": (
            "Замените домен и путь на endpoint вашей CRM. "
            "Секреты передавайте через bridge или секрет-хранилище."
        ),
    },
    {
        "id": "notion-bridge",
        "name": "Notion: создать страницу через bridge",
        "description": "Создаёт страницу или добавляет запись в Notion через OAuth bridge.",
        "kind": "http",
        "method": "POST",
        "base_url": "https://your-bridge.example.com",
        "allowed_path": "/notion/create-page",
        "requires_approval": True,
        "setup_hint": (
            "Подключите OAuth bridge с доступом к выбранной базе Notion; "
            "секреты и refresh token остаются за пределами AgentHub."
        ),
    },
    {
        "id": "google-calendar-bridge",
        "name": "Google Calendar: создать событие",
        "description": "Создаёт событие в Google Calendar через OAuth bridge с обязательным approval.",
        "kind": "http",
        "method": "POST",
        "base_url": "https://your-bridge.example.com",
        "allowed_path": "/google-calendar/create-event",
        "requires_approval": True,
        "setup_hint": (
            "Используйте отдельный OAuth bridge и ограничьте календарь; "
            "не передавайте credentials в URL или prompt."
        ),
    },
]


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
        select(IntegrationTool).where(
            IntegrationTool.id == tool_id, IntegrationTool.owner_id == workspace_owner_id(user)
        )
    )
    if not tool:
        raise AppError("TOOL_NOT_FOUND", "Tool not found", 404)
    return tool


@router.get("", response_model=list[ToolOut])
async def list_tools(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    stmt = (
        select(IntegrationTool)
        .where(IntegrationTool.owner_id == workspace_owner_id(user))
        .order_by(IntegrationTool.created_at.desc())
    )
    return list((await session.scalars(stmt)).all())


@router.get("/catalog", response_model=list[ToolTemplateOut])
async def list_tool_templates(user: User = Depends(get_current_user)):
    """Return safe starter templates; templates never contain credentials."""
    return TOOL_TEMPLATES


@router.post("", response_model=ToolOut, status_code=201)
async def create_tool(
    payload: ToolCreate,
    user: User = Depends(require_roles("admin", "manager")),
    session: AsyncSession = Depends(get_session),
):
    validate_target(payload.base_url, payload.allowed_path)
    tool = IntegrationTool(owner_id=workspace_owner_id(user), **payload.model_dump())
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


@router.post("/{tool_id}/test")
async def test_tool(
    tool_id: str,
    user: User = Depends(require_roles("admin", "manager")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Perform a side-effect-free HEAD probe against an allowlisted endpoint."""
    tool = await owned_tool(tool_id, user, session)
    url = f"{tool.base_url.rstrip('/')}/{tool.allowed_path.lstrip('/')}"
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=False) as client:
            response = await client.head(url)
        return {
            "ok": response.status_code < 500,
            "status_code": response.status_code,
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "message": "Endpoint доступен" if response.status_code < 500 else "Endpoint вернул ошибку",
        }
    except httpx.HTTPError as exc:
        return {
            "ok": False,
            "status_code": None,
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "message": str(exc)[:240] or "Не удалось подключиться",
        }
