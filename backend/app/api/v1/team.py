from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin, write_audit
from app.core.errors import AppError
from app.core.security import hash_password
from app.db.models import User
from app.db.session import get_session
from app.schemas.users import TeamUserCreate, TeamUserOut, TeamUserUpdate

router = APIRouter(prefix="/team", tags=["team"])


@router.get("", response_model=list[TeamUserOut])
async def list_team(_: User = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    return list((await session.scalars(select(User).order_by(User.created_at.asc()))).all())


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
