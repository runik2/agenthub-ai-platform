from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.agents import router as agents_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.auth import router as auth_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.logs import router as logs_router
from app.api.v1.providers import router as providers_router
from app.api.v1.settings import router as settings_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(agents_router)
api_router.include_router(providers_router)
api_router.include_router(conversations_router)
api_router.include_router(analytics_router)
api_router.include_router(logs_router)
api_router.include_router(settings_router)
