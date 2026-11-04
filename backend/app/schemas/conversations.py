from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ConversationCreate(BaseModel):
    agent_id: str
    title: str = Field(default="", max_length=255)


class ConversationUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class MessageOut(ORMModel):
    id: str
    conversation_id: str
    role: str
    content: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    model_name: str
    provider_id: str | None
    error_code: str | None
    meta: dict = Field(default_factory=dict)
    created_at: datetime


class ConversationOut(ORMModel):
    id: str
    agent_id: str
    user_id: str
    title: str
    status: str
    message_count: int
    total_tokens: int
    total_cost: float
    last_message_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationOut):
    messages: list[MessageOut] = Field(default_factory=list)


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


class UsageOut(BaseModel):
    tokens_in: int
    tokens_out: int
    total_tokens: int
    cost: float
    currency: str = "USD"
    latency_ms: int
    model_name: str
    estimated: bool = False


class SendMessageResponse(BaseModel):
    user_message: MessageOut
    assistant_message: MessageOut
    usage: UsageOut
