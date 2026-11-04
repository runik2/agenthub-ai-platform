"""Prints table names of the database referenced by DATABASE_URL (dev helper)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.db.session import get_engine  # noqa: E402


async def main() -> None:
    engine = get_engine()
    async with engine.connect() as connection:
        rows = (await connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))).all()
    print(sorted(row[0] for row in rows))
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
