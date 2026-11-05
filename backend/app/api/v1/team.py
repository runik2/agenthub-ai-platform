from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin, workspace_owner_id, write_audit
from app.config import get_settings
from app.core.errors import AppError
from app.core.security import hash_password
from app.db.models import TeamInvitation, User
from app.db.session import get_session
from app.schemas.users import (
    TeamInvitationAccept,
    TeamInvitationCreate,
    TeamInvitationOut,
    TeamUserCreate,
    TeamUserOut,
    TeamUserUpdate,
)

router = APIRouter(prefix="/team", tags=["team"])


@router.get("", response_model=list[TeamUserOut])
async def list_team(_: User = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    admin = _
    return list(
        (
            await session.scalars(
                select(User)
                .where(
                    or_(
                        User.workspace_id == workspace_owner_id(admin),
                        User.id == workspace_owner_id(admin),
                    )
                )
                .order_by(User.created_at.asc())
            )
        ).all()
    )


def _hash_token(value: str) -> str:
    return sha256(value.encode()).hexdigest()


@router.post("/invitations", response_model=TeamInvitationOut, status_code=201)
async def create_invitation(
    payload: TeamInvitationCreate,
    request: Request,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    raw = token_urlsafe(48)
    invitation = TeamInvitation(
        workspace_id=workspace_owner_id(admin),
        invited_by_id=admin.id,
        email=payload.email,
        role="viewer" if payload.role == "user" else payload.role,
        token_hash=_hash_token(raw),
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    session.add(invitation)
    await write_audit(
        session,
        request,
        admin.id,
        "team.invitation_created",
        "invitation",
        invitation.id,
        {"role": invitation.role},
    )
    await session.commit()
    await session.refresh(invitation)
    return TeamInvitationOut(
        id=invitation.id,
        email=invitation.email,
        role=invitation.role,
        expires_at=invitation.expires_at,
        invite_url=f"{get_settings().team_invite_frontend_url}?invite_token={quote(raw)}",
    )


@router.post("/invitations/accept")
async def accept_invitation(
    payload: TeamInvitationAccept,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    invitation = await session.scalar(
        select(TeamInvitation).where(TeamInvitation.token_hash == _hash_token(payload.token))
    )
    now = datetime.now(UTC)
    expires_at = (
        invitation.expires_at.replace(tzinfo=UTC)
        if invitation and invitation.expires_at.tzinfo is None
        else invitation.expires_at
        if invitation
        else None
    )
    if not invitation or invitation.accepted_at or not expires_at or expires_at <= now:
        raise AppError("INVALID_INVITATION", "Invitation is invalid or expired", 400)
    if await session.scalar(select(User).where(User.email == invitation.email)):
        raise AppError("EMAIL_IN_USE", "A user with this email already exists", 409)
    user = User(
        email=invitation.email,
        full_name=payload.full_name.strip(),
        hashed_password=hash_password(payload.password),
        role=invitation.role,
        workspace_id=invitation.workspace_id,
        is_active=True,
    )
    session.add(user)
    invitation.accepted_at = now
    await session.flush()
    await write_audit(session, request, user.id, "team.invitation_accepted", "user", user.id)
    await session.commit()
    return {"status": "accepted", "email": user.email}


@router.post("", response_model=TeamUserOut, status_code=201)
async def create_team_user(
    payload: TeamUserCreate,
    request: Request,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    user = User(
        email=payload.email.strip().lower(),
        full_name=payload.full_name.strip(),
        hashed_password=hash_password(payload.password),
        role=payload.role,
        workspace_id=workspace_owner_id(admin),
        is_active=True,
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError("EMAIL_IN_USE", "A user with this email already exists", 409) from exc
    await write_audit(session, request, admin.id, "team.user_created", "user", user.id, {"role": user.role})
    await session.commit()
    await session.refresh(user)
    return user


@router.patch("/{user_id}", response_model=TeamUserOut)
async def update_team_user(
    user_id: str,
    payload: TeamUserUpdate,
    request: Request,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    user = await session.get(User, user_id)
    if not user:
        raise AppError("USER_NOT_FOUND", "User not found", 404)
    values = payload.model_dump(exclude_unset=True)
    if user.id == admin.id and values.get("is_active") is False:
        raise AppError("SELF_DISABLE", "You cannot disable your own account", 409)
    changing_admin = values.get("role") not in (None, "admin") or values.get("is_active") is False
    if user.role == "admin" and changing_admin:
        admins = await session.scalar(
            select(func.count(User.id)).where(User.role == "admin", User.is_active.is_(True))
        )
        if (admins or 0) <= 1:
            raise AppError("LAST_ADMIN", "At least one active administrator is required", 409)
    for key, value in values.items():
        setattr(user, key, value)
    await write_audit(session, request, admin.id, "team.user_updated", "user", user.id, values)
    await session.commit()
    await session.refresh(user)
    return user
