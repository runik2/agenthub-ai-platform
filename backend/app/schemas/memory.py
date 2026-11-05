from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MemoryCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    agent_id: str | None = None
    category: str = Field(default="fact", max_length=40)
    is_pinned: bool = False


class MemoryUpdate(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=4000)
    category: str | None = Field(default=None, max_length=40)
    is_pinned: bool | None = None


class MemoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    agent_id: str | None
    content: str
    category: str
    source: str
    is_pinned: bool
    created_at: datetime
    updated_at: datetime
