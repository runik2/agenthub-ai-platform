from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PromptVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    agent_id: str
    version: int
    system_prompt: str
    note: str
    author_id: str | None = None
    author_name: str | None = None
    created_at: datetime


class PromptDiffOut(BaseModel):
    from_version: int
    to_version: int
    unified_diff: str


class PromptRollback(BaseModel):
    note: str = Field(default="Restored from history", max_length=255)
