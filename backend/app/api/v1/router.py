from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.agents import router as agents_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.auth import router as auth_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.logs import router as logs_router
from app.api.v1.memories import router as memories_router
from app.api.v1.providers import router as providers_router
from app.api.v1.schedules import router as schedules_router
from app.api.v1.settings import router as settings_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.team import router as team_router
from app.api.v1.tools import router as tools_router
from app.api.v1.workflows import router as workflows_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(agents_router)
api_router.include_router(providers_router)
api_router.include_router(conversations_router)
api_router.include_router(analytics_router)
api_router.include_router(logs_router)
api_router.include_router(knowledge_router)
api_router.include_router(memories_router)
api_router.include_router(settings_router)
api_router.include_router(tasks_router)
api_router.include_router(team_router)
api_router.include_router(tools_router)
api_router.include_router(workflows_router)
api_router.include_router(schedules_router)
