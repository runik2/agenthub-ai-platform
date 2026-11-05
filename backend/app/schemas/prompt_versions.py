from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PromptVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    agent_id: str
    version: int
    system_prompt: str
    note: str
    created_at: datetime


class PromptRollback(BaseModel):
    note: str = Field(default="Restored from history", max_length=255)
