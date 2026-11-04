from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.config import get_settings
from app.db.models import User
from app.queue.inprocess import InProcessQueue

router = APIRouter(prefix="/settings", tags=["settings"])

_queue = InProcessQueue()


@router.get("")
async def read_settings(_: User = Depends(get_current_user)) -> dict:
    settings = get_settings()
    return {
        "app_name": settings.app_name,
        "version": settings.version,
        "app_mode": settings.app_mode,
        "database_backend": "sqlite" if settings.is_sqlite else "postgresql",
        "ollama_base_url": settings.ollama_base_url,
        "seed_demo_data": settings.seed_demo_data,
        "features": {
            "chat": True,
            "agents": True,
            "providers": True,
            "queue": False,
            "workflows": False,
            "tools": False,
            "schedules": False,
            "analytics_full": False,
        },
        "runtime": {
            "queue_backend": "arq+redis" if settings.is_docker_mode else _queue.name,
            "scheduler": "separate process" if settings.is_docker_mode else "in-process",
        },
        "docker_verified": False,
    }
