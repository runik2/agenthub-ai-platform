"""Cron scheduler shared by local lifespan and docker scheduler process.

Local mode schedules inside the API process (`app/queue/inprocess.py`). The
docker contour runs this file as its own container so that scheduled agent runs
survive API restarts. No schedules exist yet — the loop only reports health.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select

from app.config import get_settings
from app.db.models import Schedule, Task
from app.db.session import dispose_engine, get_session_factory, init_db
from app.queue.arq import ArqTaskQueue
from app.queue.inprocess import InProcessQueue
from app.queue.runtime import get_queue, set_queue
from app.services.tasks import execute_task

logger = logging.getLogger("agenthub.scheduler")


async def main(interval_seconds: int = 30) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logger.info("scheduler started")
    await init_db()
    settings = get_settings()
    queue = ArqTaskQueue(settings.redis_url) if settings.is_docker_mode else InProcessQueue()
    if isinstance(queue, InProcessQueue):
        queue.register("execute_task", lambda p: execute_task(p["task_id"]))
    set_queue(queue)
    queue.start()
    try:
        while True:
            await tick()
            await asyncio.sleep(interval_seconds)
    finally:
        await queue.stop()
        await dispose_engine()


async def tick(now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    created = 0
    try:
        from croniter import croniter
    except ImportError:
        croniter = None
    async with get_session_factory()() as session:
        rows = (await session.scalars(select(Schedule).where(Schedule.enabled))).all()
        for schedule in rows:
            due = schedule.last_run_at is None
            if croniter and schedule.last_run_at:
                due = croniter(schedule.cron, schedule.last_run_at).get_next(datetime) <= now
            if not due:
                continue
            task = Task(
                owner_id=schedule.owner_id, workflow_id=schedule.workflow_id, name=schedule.name, input=""
            )
            session.add(task)
            schedule.last_run_at = now
            schedule.run_count += 1
            created += 1
            await session.flush()
            task.status = "queued"
            # Commit the claim before publishing.  SQLite serializes this write,
            # so a second tick cannot observe the old last_run_at.
            await session.commit()
            try:
                await get_queue().enqueue("execute_task", {"task_id": task.id})
            except Exception as exc:
                task.status, task.error = "failed", f"queue enqueue failed: {exc}"
                await session.commit()
        retry_tasks = (
            await session.scalars(
                select(Task).where(
                    Task.status == "pending",
                    Task.next_run_at.is_not(None),
                    Task.next_run_at <= now,
                )
            )
        ).all()
        for task in retry_tasks:
            task.status = "queued"
            await session.commit()
            try:
                await get_queue().enqueue("execute_task", {"task_id": task.id})
            except Exception as exc:
                task.status, task.error = "pending", f"queue enqueue failed: {exc}"
                task.next_run_at = now
                await session.commit()
        await session.commit()
    return created


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
