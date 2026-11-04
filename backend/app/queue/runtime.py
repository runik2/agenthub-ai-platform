from __future__ import annotations

from typing import Any

_queue: Any = None


def set_queue(queue: Any) -> None:
    global _queue
    _queue = queue


def get_queue() -> Any:
    if _queue is None:
        raise RuntimeError("queue is not started")
    return _queue
