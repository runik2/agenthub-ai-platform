from __future__ import annotations

from fastapi import Query
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession


class Pagination:
    def __init__(
        self,
        page: int = Query(1, ge=1),
        page_size: int = Query(12, ge=1, le=100),
    ) -> None:
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


async def paginate(
    session: AsyncSession, stmt: Select, pagination: Pagination
) -> tuple[list, int, int]:
    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = int(await session.scalar(count_stmt) or 0)
    rows = (
        await session.scalars(stmt.offset(pagination.offset).limit(pagination.page_size))
    ).all()
    pages = (total + pagination.page_size - 1) // pagination.page_size if total else 0
    return list(rows), total, pages
