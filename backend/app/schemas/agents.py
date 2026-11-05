from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel

AgentStatus = Literal["draft", "active", "archived"]


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    system_prompt: str = Field(min_length=1, max_length=8000)
    greeting: str = Field(default="", max_length=2000)
    provider_id: str | None = None
    fallback_provider_id: str | None = None
    model_name: str = Field(default="", max_length=255)
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=1024, ge=16, le=32000)
    status: AgentStatus = "draft"
    avatar_color: str = Field(default="#3B82F6", pattern=r"^#[0-9a-fA-F]{6}$")
    tags: list[str] = Field(default_factory=list, max_length=12)

    @field_validator("tags")
    @classmethod
    def _clean_tags(cls, value: list[str]) -> list[str]:
        cleaned = [tag.strip()[:32] for tag in value if tag and tag.strip()]
        return list(dict.fromkeys(cleaned))[:12]


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    system_prompt: str | None = Field(default=None, min_length=1, max_length=8000)
    greeting: str | None = Field(default=None, max_length=2000)
    provider_id: str | None = None
    fallback_provider_id: str | None = None
    model_name: str | None = Field(default=None, max_length=255)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=16, le=32000)
    status: AgentStatus | None = None
    avatar_color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    tags: list[str] | None = None


class AgentOut(ORMModel):
    id: str
    name: str
    slug: str
    description: str
    system_prompt: str
    greeting: str
    provider_id: str | None
    fallback_provider_id: str | None
    model_name: str
    temperature: float
    max_tokens: int
    status: str
    avatar_color: str
    tags: list[str]
    is_template: bool
    template_slug: str | None
    owner_id: str
    created_at: datetime
    updated_at: datetime


class AgentTemplate(BaseModel):
    slug: str
    name: str
    description: str
    system_prompt: str
    greeting: str
    model_name: str
    temperature: float
    max_tokens: int
    tags: list[str]
    avatar_color: str
    category: str
