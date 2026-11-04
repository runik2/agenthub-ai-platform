from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ProviderKind = Literal["ollama", "openai_compatible"]


class ProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: ProviderKind = "ollama"
    base_url: str = Field(default="", max_length=500)
    api_key: str | None = Field(default=None, max_length=500)
    default_model: str = Field(default="", max_length=255)
    input_price_per_1m: float = Field(default=0, ge=0, le=100000)
    output_price_per_1m: float = Field(default=0, ge=0, le=100000)
    is_active: bool = True
    extra_headers: dict[str, str] = Field(default_factory=dict)


class ProviderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    kind: ProviderKind | None = None
    base_url: str | None = Field(default=None, max_length=500)
    api_key: str | None = Field(default=None, max_length=500)
    default_model: str | None = Field(default=None, max_length=255)
    input_price_per_1m: float | None = Field(default=None, ge=0, le=100000)
    output_price_per_1m: float | None = Field(default=None, ge=0, le=100000)
    is_active: bool | None = None
    extra_headers: dict[str, str] | None = None


class ProviderOut(BaseModel):
    id: str
    name: str
    kind: str
    base_url: str
    default_model: str
    input_price_per_1m: float
    output_price_per_1m: float
    is_active: bool
    has_api_key: bool
    api_key_hint: str | None
    last_checked_at: datetime | None
    last_check_status: str
    last_check_message: str | None
    models_cache: list[str]
    created_at: datetime
    updated_at: datetime


class ConnectionResult(BaseModel):
    status: str
    message: str
    models: list[str] = Field(default_factory=list)
    latency_ms: int = 0


class ModelsResult(BaseModel):
    models: list[str]
    updated_at: datetime
