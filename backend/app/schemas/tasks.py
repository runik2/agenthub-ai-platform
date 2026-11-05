from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TaskCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    input: str = ""
    agent_id: str | None = None
    workflow_id: str | None = None
    max_retries: int = Field(default=2, ge=0, le=10)


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    input: str
    agent_id: str | None
    workflow_id: str | None
    status: str
    result: str | None
    error: str | None
    requires_approval: bool
    approval_note: str | None
    approved_at: datetime | None
    attempts: int
    created_at: datetime


class TaskApprovalEdit(BaseModel):
    input: str = Field(min_length=0, max_length=50_000)


class Step(BaseModel):
    id: str
    type: str = "agent"  # agent | tool | condition | approval | parallel
    agent_id: str | None = None
    prompt: str = ""
    tool: str | None = None
    tool_id: str | None = None
    template: str | None = None
    path: str | None = None
    allowlist: list[str] = Field(default_factory=list)
    condition: str | dict | None = None
    branch: str | None = None
    on_true: str = "true"
    on_false: str = "false"
    retries: int = Field(default=0, ge=0, le=3)
    timeout_seconds: int = Field(default=15, ge=1, le=120)
    branches: list[dict] = Field(default_factory=list, max_length=8)


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = ""
    steps: list[Step] = []
    enabled: bool = True


class WorkflowOut(WorkflowCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    owner_id: str
    created_at: datetime


class ScheduleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    workflow_id: str
    cron: str = "*/15 * * * *"
    enabled: bool = True


class ScheduleOut(ScheduleCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    owner_id: str
    run_count: int
    last_run_at: datetime | None
    created_at: datetime
