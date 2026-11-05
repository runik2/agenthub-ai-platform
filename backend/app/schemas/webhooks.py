from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WebhookCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=3, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    workflow_id: str
    enabled: bool = True
    allowed_ips: list[str] = Field(default_factory=list, max_length=32)


class WebhookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    slug: str
    workflow_id: str
    enabled: bool
    allowed_ips: list[str]
    last_received_at: datetime | None
    created_at: datetime


class WebhookCreated(WebhookOut):
    secret: str


class WebhookTestPayload(BaseModel):
    payload: dict = Field(default_factory=dict)


class WebhookTestOut(BaseModel):
    status: str
    task_id: str
    delivery_id: str


class DeliveryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    endpoint_id: str
    event_id: str | None
    task_id: str | None
    status: str
    signature_valid: bool
    payload: dict
    error: str | None
    created_at: datetime
