"""Account endpoints."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from psycopg import AsyncConnection

from app.core.register_user import register_user
from app.dependencies import db
from app.schemas.auth import RegisterRequest, UserResponse

router = APIRouter(prefix="/auth", tags=["account"])

Db = Annotated[AsyncConnection[Any], Depends(db)]


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, conn: Db) -> UserResponse:
    user = await register_user(conn, str(payload.email), payload.password)
    return UserResponse(**user)
