from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse, PlainTextResponse

from app.config import get_settings
from app.core.metrics import metrics
from app.db.session import check_database
from app.queue.runtime import get_queue

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready() -> JSONResponse:
    settings = get_settings()
    database = "ok"
    queue_status = "ok"
    try:
        await check_database()
    except Exception as exc:  # noqa: BLE001
        logging.getLogger("agenthub.health").warning("database not ready: %s", exc)
        database = "error"
    try:
        queue_status = "ok" if await get_queue().health() else "error"
    except Exception as exc:  # noqa: BLE001
        logging.getLogger("agenthub.health").warning("queue not ready: %s", exc)
        queue_status = "error"
    payload = {
        "status": "ok" if database == "ok" and queue_status == "ok" else "degraded",
        "db": database,
        "queue": queue_status,
        "mode": settings.app_mode,
        "version": settings.version,
    }
    return JSONResponse(
        status_code=200 if database == "ok" and queue_status == "ok" else 503, content=payload
    )


@router.get("/metrics", include_in_schema=False)
async def prometheus_metrics() -> PlainTextResponse:
    return PlainTextResponse(metrics.render(), media_type="text/plain; version=0.0.4")
