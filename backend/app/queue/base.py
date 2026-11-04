from __future__ import annotations

from typing import Any, Protocol


class TaskQueue(Protocol):
    """Queue boundary used from stage 3 onwards.

    ``APP_MODE=local`` resolves to :class:`InProcessQueue`, ``APP_MODE=docker``
    resolves to the ARQ/Redis adapter which is shipped but not exercised here.
    """

    name: str

    async def enqueue(self, task_name: str, payload: dict[str, Any]) -> str: ...

    async def health(self) -> bool: ...

    def start(self) -> None: ...

    async def stop(self) -> None: ...
