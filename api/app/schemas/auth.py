"""Request and response shapes for the account endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

# Long enough to be worth an Argon2id hash, short enough not to be a lecture.
MIN_PASSWORD_LENGTH = 8


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=1024)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    token: str
    expires_at: datetime


class UserResponse(BaseModel):
    id: UUID
    email: str
    created_at: datetime
