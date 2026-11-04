from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: str
    user_id: str | None
    action: str
    entity_type: str
    entity_id: str | None
    ip_address: str | None
    payload: dict
    created_at: datetime

    model_config = {"from_attributes": True}
