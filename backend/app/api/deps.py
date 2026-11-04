from __future__ import annotations

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import decode_access_token
from app.db.models import AuditLog, User
from app.db.session import get_session

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    if credentials is None or not credentials.credentials:
        raise AppError("UNAUTHORIZED", "Missing bearer token", 401)
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise AppError("UNAUTHORIZED", "Invalid or expired token", 401)
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise AppError("UNAUTHORIZED", "User not found or disabled", 401)
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise AppError("FORBIDDEN", "Administrator access required", 403)
    return user


def client_meta(request: Request) -> tuple[str | None, str | None]:
    ip = request.client.host if request.client else None
    return ip, request.headers.get("user-agent")


async def write_audit(
    session: AsyncSession,
    request: Request | None,
    user_id: str | None,
    action: str,
    entity_type: str = "",
    entity_id: str | None = None,
    payload: dict | None = None,
) -> None:
    ip, agent = client_meta(request) if request is not None else (None, None)
    session.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            ip_address=ip,
            user_agent=agent,
            payload=payload or {},
        )
    )
