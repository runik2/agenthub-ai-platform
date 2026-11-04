from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from pathlib import Path

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db import models as _models  # noqa: F401  (register mappers)
from app.db.base import Base

logger = logging.getLogger("agenthub.db")

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _prepare_sqlite_path(url: str) -> None:
    prefix = "sqlite+aiosqlite:///"
    if not url.startswith(prefix):
        return
    raw = url[len(prefix) :]
    if raw in {"", ":memory:"}:
        return
    path = Path(raw)
    if not path.is_absolute():
        path = Path.cwd() / path
    path.parent.mkdir(parents=True, exist_ok=True)


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        if settings.is_sqlite:
            _prepare_sqlite_path(settings.database_url)
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.db_echo,
            pool_pre_ping=True,
            future=True,
        )
        if settings.is_sqlite:

            @event.listens_for(_engine.sync_engine, "connect")
            def _sqlite_pragma(dbapi_connection, _record):  # pragma: no cover - driver hook
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.close()

        logger.info("database engine created for mode=%s", settings.app_mode)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(bind=get_engine(), expire_on_commit=False, class_=AsyncSession)
    return _session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create tables for the running mode.

    Local mode uses ``create_all`` so a fresh checkout runs with no CLI steps.
    The Alembic tree in ``backend/alembic`` mirrors these models for PostgreSQL.
    """
    engine = get_engine()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def check_database() -> bool:
    engine = get_engine()
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    return True


async def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
