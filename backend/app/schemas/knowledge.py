from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=200_000)
    agent_id: str | None = None


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    source_type: str
    agent_id: str | None
    chunk_count: int
    version: int
    created_at: datetime
    updated_at: datetime


class SearchResult(BaseModel):
    document_id: str
    title: str
    chunk_index: int
    content: str
    score: float


class DocumentVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    document_id: str
    version: int
    chunk_count: int
    created_at: datetime
