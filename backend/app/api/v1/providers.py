from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, write_audit
from app.config import get_settings
from app.core.crypto import encrypt_value, key_hint
from app.core.errors import AppError
from app.core.pagination import Pagination, paginate
from app.db.models import LLMProvider, User
from app.db.session import get_session
from app.schemas.common import Page, StatusResponse
from app.schemas.providers import (
    ConnectionResult,
    ModelsResult,
    ProviderCreate,
    ProviderOut,
    ProviderUpdate,
)
from app.services import llm

router = APIRouter(prefix="/providers", tags=["providers"])


def provider_out(provider: LLMProvider) -> ProviderOut:
    return ProviderOut(
        id=provider.id,
        name=provider.name,
        kind=provider.kind,
        base_url=provider.base_url,
        default_model=provider.default_model,
        input_price_per_1m=float(provider.input_price_per_1m or 0),
        output_price_per_1m=float(provider.output_price_per_1m or 0),
        is_active=provider.is_active,
        has_api_key=bool(provider.api_key_encrypted),
        api_key_hint=provider.api_key_hint,
        last_checked_at=provider.last_checked_at,
        last_check_status=provider.last_check_status,
        last_check_message=provider.last_check_message,
        models_cache=list(provider.models_cache or []),
        created_at=provider.created_at,
        updated_at=provider.updated_at,
    )


async def _get_provider(session: AsyncSession, provider_id: str) -> LLMProvider:
    provider = await session.get(LLMProvider, provider_id)
    if provider is None:
        raise AppError("PROVIDER_NOT_FOUND", "Provider not found", 404)
    return provider


def _apply_credentials(provider: LLMProvider, api_key: str | None) -> None:
    if api_key is None:
        return
    if not api_key.strip():
        provider.api_key_encrypted = None
        provider.api_key_hint = None
        return
    provider.api_key_encrypted = encrypt_value(api_key.strip())
    provider.api_key_hint = key_hint(api_key.strip())


@router.get("", response_model=Page[ProviderOut])
async def list_providers(
    pagination: Pagination = Depends(),
    kind: str = Query(default="", max_length=40),
    is_active: bool | None = Query(default=None),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Page[ProviderOut]:
    stmt = select(LLMProvider)
    if kind.strip():
        stmt = stmt.where(LLMProvider.kind == kind.strip())
    if is_active is not None:
        stmt = stmt.where(LLMProvider.is_active.is_(is_active))
    stmt = stmt.order_by(LLMProvider.created_at.asc())
    rows, total, pages = await paginate(session, stmt, pagination)
    return Page[ProviderOut](
        items=[provider_out(row) for row in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        pages=pages,
    )


@router.post("", response_model=ProviderOut, status_code=201)
async def create_provider(
    payload: ProviderCreate,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ProviderOut:
    settings = get_settings()
    base_url = payload.base_url.strip()
    if not base_url and payload.kind == "ollama":
        base_url = settings.ollama_base_url
    if not base_url:
        raise AppError("PROVIDER_BASE_URL_REQUIRED", "base_url is required", 400)
    provider = LLMProvider(
        name=payload.name.strip(),
        kind=payload.kind,
        base_url=base_url.rstrip("/"),
        default_model=payload.default_model.strip(),
        input_price_per_1m=Decimal(str(payload.input_price_per_1m)),
        output_price_per_1m=Decimal(str(payload.output_price_per_1m)),
        is_active=payload.is_active,
        extra_headers=payload.extra_headers,
        models_cache=[],
    )
    _apply_credentials(provider, payload.api_key)
    session.add(provider)
    await session.flush()
    await write_audit(
        session, request, user.id, "provider.created", "provider", provider.id, {"kind": provider.kind}
    )
    await session.commit()
    await session.refresh(provider)
    return provider_out(provider)


@router.get("/{provider_id}", response_model=ProviderOut)
async def get_provider(
    provider_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ProviderOut:
    return provider_out(await _get_provider(session, provider_id))


@router.patch("/{provider_id}", response_model=ProviderOut)
async def update_provider(
    provider_id: str,
    payload: ProviderUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ProviderOut:
    provider = await _get_provider(session, provider_id)
    data = payload.model_dump(exclude_unset=True)
    api_key = data.pop("api_key", None)
    _apply_credentials(provider, api_key)
    if "input_price_per_1m" in data and data["input_price_per_1m"] is not None:
        data["input_price_per_1m"] = Decimal(str(data["input_price_per_1m"]))
    if "output_price_per_1m" in data and data["output_price_per_1m"] is not None:
        data["output_price_per_1m"] = Decimal(str(data["output_price_per_1m"]))
    if "base_url" in data and data["base_url"]:
        data["base_url"] = data["base_url"].strip().rstrip("/")
    for field, value in data.items():
        if value is not None:
            setattr(provider, field, value)
    await write_audit(session, request, user.id, "provider.updated", "provider", provider.id)
    await session.commit()
    await session.refresh(provider)
    return provider_out(provider)


@router.delete("/{provider_id}", response_model=StatusResponse)
async def delete_provider(
    provider_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> StatusResponse:
    provider = await _get_provider(session, provider_id)
    await session.delete(provider)
    await write_audit(session, request, user.id, "provider.deleted", "provider", provider_id)
    await session.commit()
    return StatusResponse()


@router.post("/{provider_id}/test-connection", response_model=ConnectionResult)
async def test_connection(
    provider_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ConnectionResult:
    provider = await _get_provider(session, provider_id)
    ok, message, models, latency_ms = await llm.test_connection(provider)
    provider.last_checked_at = datetime.now(UTC)
    provider.last_check_status = "ok" if ok else "error"
    provider.last_check_message = message
    if ok and models:
        provider.models_cache = models
    await write_audit(
        session, request, user.id, "provider.checked", "provider", provider.id,
        {"status": provider.last_check_status},
    )
    await session.commit()
    return ConnectionResult(
        status=provider.last_check_status, message=message, models=models, latency_ms=latency_ms
    )


@router.post("/{provider_id}/refresh-models", response_model=ModelsResult)
async def refresh_models(
    provider_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ModelsResult:
    provider = await _get_provider(session, provider_id)
    try:
        models = await llm.fetch_models(provider)
    except llm.LLMError as exc:
        provider.last_check_status = "error"
        provider.last_check_message = exc.message
        provider.last_checked_at = datetime.now(UTC)
        await session.commit()
        raise AppError(exc.code, exc.message, 502) from exc
    provider.models_cache = models
    provider.last_check_status = "ok"
    provider.last_check_message = f"{len(models)} models available"
    provider.last_checked_at = datetime.now(UTC)
    await session.commit()
    return ModelsResult(models=models, updated_at=provider.last_checked_at)
