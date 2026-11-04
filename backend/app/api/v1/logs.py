from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.pagination import Pagination, paginate
from app.db.models import AuditLog, User
from app.db.session import get_session
from app.schemas.common import Page
from app.schemas.logs import AuditLogOut

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("", response_model=Page[AuditLogOut])
async def list_logs(
    pagination: Pagination = Depends(),
    action: str = Query(default="", max_length=100),
    entity_type: str = Query(default="", max_length=100),
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Page[AuditLogOut]:
    stmt = select(AuditLog)
    if action.strip():
        stmt = stmt.where(AuditLog.action.ilike(f"%{action.strip()}%"))
    if entity_type.strip():
        stmt = stmt.where(AuditLog.entity_type == entity_type.strip())
    stmt = stmt.order_by(AuditLog.created_at.desc())
    rows, total, pages = await paginate(session, stmt, pagination)
    return Page[AuditLogOut](
        items=[AuditLogOut.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        pages=pages,
    )
