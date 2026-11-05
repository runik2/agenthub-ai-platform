from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Role = Literal["admin", "manager", "operator", "viewer", "user"]


class TeamUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


class TeamUserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    full_name: str = Field(default="", max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: Role = "operator"


class TeamUserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    role: Role | None = None
    is_active: bool | None = None

    @field_validator("role")
    @classmethod
    def normalize_legacy_role(cls, value: Role | None) -> Role | None:
        return "viewer" if value == "user" else value


class TeamInvitationCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    role: Role = "operator"

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class TeamInvitationOut(BaseModel):
    id: str
    email: str
    role: str
    expires_at: datetime
    invite_url: str


class TeamInvitationAccept(BaseModel):
    token: str = Field(min_length=20, max_length=500)
    full_name: str = Field(default="", max_length=255)
    password: str = Field(min_length=8, max_length=128)
