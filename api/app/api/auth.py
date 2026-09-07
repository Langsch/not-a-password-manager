"""Account endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.core.login_user import login_user
from app.core.register_user import register_user
from app.core.sessions import close_session
from app.dependencies import Caller, Db, Token
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["account"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, conn: Db) -> UserResponse:
    user = await register_user(conn, str(payload.email), payload.password)
    return UserResponse(**user)


@router.post("/login")
async def login(payload: LoginRequest, conn: Db) -> TokenResponse:
    token, expires_at = await login_user(conn, str(payload.email), payload.password)
    return TokenResponse(token=token, expires_at=expires_at)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(token: Token, caller: Caller, conn: Db) -> Response:
    await close_session(conn, token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
