from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, write_audit
from app.config import get_settings
from app.core.errors import AppError
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import RefreshSession, User
from app.db.session import get_session
from app.schemas.auth import LoginRequest, RefreshRequest, SetupRequest, SetupStatus, TokenResponse, UserOut
from app.services.bootstrap import user_count

router = APIRouter(prefix="/auth", tags=["auth"])


def token_hash(value: str) -> str:
    return sha256(value.encode()).hexdigest()


async def issue_tokens(user: User, request: Request, session: AsyncSession) -> TokenResponse:
    raw = token_urlsafe(48)
    ip = request.client.host if request.client else None
    session.add(
        RefreshSession(
            user_id=user.id,
            token_hash=token_hash(raw),
            expires_at=datetime.now(UTC) + timedelta(days=get_settings().refresh_token_ttl_days),
            user_agent=request.headers.get("user-agent"),
            ip_address=ip,
        )
    )
    return TokenResponse(
        access_token=create_access_token(user.id), refresh_token=raw, user=UserOut.model_validate(user)
    )


@router.get("/setup-status", response_model=SetupStatus)
async def setup_status(session: AsyncSession = Depends(get_session)) -> SetupStatus:
    return SetupStatus(needs_setup=await user_count(session) == 0)


@router.post("/setup", response_model=TokenResponse, status_code=201)
async def setup(
    payload: SetupRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    if await user_count(session) > 0:
        raise AppError("SETUP_ALREADY_DONE", "Administrator already exists", 409)
    user = User(
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role="admin",
        is_active=True,
    )
    session.add(user)
    await session.flush()
    await write_audit(session, request, user.id, "auth.setup", "user", user.id)
    await session.commit()
    await session.refresh(user)
    response = await issue_tokens(user, request, session)
    await session.commit()
    return response


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    user = await session.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise AppError("INVALID_CREDENTIALS", "Invalid email or password", 401)
    if not user.is_active:
        raise AppError("USER_DISABLED", "This account is disabled", 403)
    user.last_login_at = datetime.now(UTC)
    await write_audit(session, request, user.id, "auth.login", "user", user.id)
    await session.commit()
    await session.refresh(user)
    response = await issue_tokens(user, request, session)
    await session.commit()
    return response


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest, request: Request, session: AsyncSession = Depends(get_session)
) -> TokenResponse:
    record = await session.scalar(
        select(RefreshSession).where(RefreshSession.token_hash == token_hash(payload.refresh_token))
    )
    now = datetime.now(UTC)
    expires_at = (
        record.expires_at.replace(tzinfo=UTC)
        if record and record.expires_at.tzinfo is None
        else record.expires_at
        if record
        else None
    )
    if not record or record.revoked_at or expires_at <= now:
        raise AppError("INVALID_REFRESH_TOKEN", "Refresh session is invalid or expired", 401)
    user = await session.get(User, record.user_id)
    if not user or not user.is_active:
        raise AppError("USER_DISABLED", "This account is disabled", 403)
    record.revoked_at = now
    response = await issue_tokens(user, request, session)
    await session.commit()
    return response


@router.post("/logout")
async def logout(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    await write_audit(session, request, user.id, "auth.logout", "user", user.id)
    await session.commit()
    return {"status": "ok"}


@router.post("/logout-all")
async def logout_all(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    rows = (
        await session.scalars(
            select(RefreshSession).where(
                RefreshSession.user_id == user.id, RefreshSession.revoked_at.is_(None)
            )
        )
    ).all()
    now = datetime.now(UTC)
    for row in rows:
        row.revoked_at = now
    await write_audit(session, request, user.id, "auth.logout_all", "user", user.id, {"sessions": len(rows)})
    await session.commit()
    return {"status": "ok", "revoked": str(len(rows))}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)
