from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ToolCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    kind: str = Field(default="http", pattern="^(http|webhook)$")
    method: str = Field(default="POST", pattern="^(GET|POST|PUT|PATCH|DELETE)$")
    base_url: str = Field(min_length=8, max_length=500)
    allowed_path: str = Field(default="/", min_length=1, max_length=300)
    requires_approval: bool = True
    is_active: bool = True

    @field_validator("method")
    @classmethod
    def normalize_method(cls, value: str) -> str:
        return value.upper()


class ToolUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    method: str | None = Field(default=None, pattern="^(GET|POST|PUT|PATCH|DELETE)$")
    base_url: str | None = Field(default=None, min_length=8, max_length=500)
    allowed_path: str | None = Field(default=None, min_length=1, max_length=300)
    requires_approval: bool | None = None
    is_active: bool | None = None

    @field_validator("method")
    @classmethod
    def normalize_method(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class ToolOut(ToolCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    owner_id: str
    created_at: datetime
    updated_at: datetime


class ToolTemplateOut(BaseModel):
    id: str
    name: str
    description: str
    kind: str
    method: str
    base_url: str
    allowed_path: str
    requires_approval: bool
    setup_hint: str
