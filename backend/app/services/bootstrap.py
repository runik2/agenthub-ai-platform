from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security import hash_password
from app.db.models import User

logger = logging.getLogger("agenthub.bootstrap")


async def user_count(session: AsyncSession) -> int:
    return int(await session.scalar(select(func.count(User.id))) or 0)


async def ensure_bootstrap_admin(session: AsyncSession) -> User | None:
    """Create the first administrator when the database has no users at all."""
    if await user_count(session) > 0:
        return None
    settings = get_settings()
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        logger.info("no users yet and no bootstrap administrator configured")
        return None
    admin = User(
        email=settings.bootstrap_admin_email.lower(),
        hashed_password=hash_password(settings.bootstrap_admin_password),
        full_name=settings.bootstrap_admin_name,
        role="admin",
        is_active=True,
    )
    session.add(admin)
    await session.flush()
    admin.workspace_id = admin.id
    await session.commit()
    await session.refresh(admin)
    logger.info("bootstrap administrator created: %s", admin.email)
    return admin
