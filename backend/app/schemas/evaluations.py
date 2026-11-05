from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class EvaluationCaseCreate(BaseModel):
    agent_id: str
    name: str = Field(min_length=1, max_length=255)
    prompt: str = Field(min_length=1, max_length=8000)
    expected: str = Field(default="", max_length=2000)
    enabled: bool = True


class EvaluationCaseOut(EvaluationCaseCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    owner_id: str
    created_at: datetime


class EvaluationRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    case_id: str
    agent_id: str
    prompt_version_id: str | None = None
    status: str
    passed: bool
    output: str
    latency_ms: int
    cost: Decimal
    error: str | None
    created_at: datetime
