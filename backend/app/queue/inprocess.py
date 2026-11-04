from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger("agenthub.queue")

Handler = Callable[[dict[str, Any]], Awaitable[None]]


class InProcessQueue:
    """asyncio queue living inside the API process (default local mode).

    States are kept in memory only; the durable record of work lives in the
    database when task tables arrive in stage 3.
    """

    name = "inprocess"

    def __init__(self, maxsize: int = 100) -> None:
        self._queue: asyncio.Queue[tuple[str, str, dict[str, Any]]] = asyncio.Queue(maxsize)
        self._handlers: dict[str, Handler] = {}
        self._worker: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    def register(self, task_name: str, handler: Handler) -> None:
        self._handlers[task_name] = handler

    async def enqueue(self, task_name: str, payload: dict[str, Any]) -> str:
        job_id = str(uuid.uuid4())
        await self._queue.put((job_id, task_name, payload))
        return job_id

    async def _run(self) -> None:
        while not self._stopping.is_set():
            try:
                job_id, task_name, payload = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except TimeoutError:
                continue
            handler = self._handlers.get(task_name)
            if handler is None:
                logger.warning("no handler registered for task %s", task_name)
                continue
            try:
                await handler(payload)
            except Exception:
                logger.exception("task %s (%s) failed", task_name, job_id)
            finally:
                self._queue.task_done()

    def start(self) -> None:
        if self._worker is None:
            self._stopping.clear()
            self._worker = asyncio.create_task(self._run(), name="agenthub-inprocess-queue")

    async def stop(self) -> None:
        self._stopping.set()
        if self._worker is not None:
            await asyncio.gather(self._worker, return_exceptions=True)
            self._worker = None

    async def health(self) -> bool:
        return not self._stopping.is_set()
