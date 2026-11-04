from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, write_audit
from app.core.errors import AppError
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import User
from app.db.session import get_session
from app.schemas.auth import LoginRequest, SetupRequest, SetupStatus, TokenResponse, UserOut
from app.services.bootstrap import user_count

router = APIRouter(prefix="/auth", tags=["auth"])


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
    return TokenResponse(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


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
    return TokenResponse(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.post("/logout")
async def logout(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    await write_audit(session, request, user.id, "auth.logout", "user", user.id)
    await session.commit()
    return {"status": "ok"}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)
