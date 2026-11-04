from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel


def _check_email(value: str) -> str:
    value = value.strip().lower()
    if "@" not in value or value.startswith("@") or value.endswith("@") or len(value) > 255:
        raise ValueError("invalid email address")
    return value



class UserOut(ORMModel):
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime


class SetupStatus(BaseModel):
    needs_setup: bool


class SetupRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(default="", max_length=255)

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        return _check_email(value)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        return _check_email(value)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
