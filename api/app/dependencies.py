"""Shared route dependencies."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg import AsyncConnection

from app.core.sessions import touch_session
from app.domain.errors import Unauthenticated

# auto_error=False so a missing header raises our Unauthenticated rather than
# FastAPI's own 403, which would leave through a different shape.
bearer = HTTPBearer(auto_error=False)


async def db(request: Request) -> AsyncIterator[AsyncConnection[Any]]:
    """A connection from the pool, committed on success and rolled back on error."""
    async with request.app.state.pool.connection() as conn:
        yield conn


Db = Annotated[AsyncConnection[Any], Depends(db)]


async def bearer_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> str:
    if credentials is None or not credentials.credentials:
        raise Unauthenticated
    return credentials.credentials


Token = Annotated[str, Depends(bearer_token)]


async def caller(token: Token, conn: Db) -> int:
    """The signed-in user's internal id, renewing their session on the way.

    Everything downstream works with this int; the public UUID never appears in
    a foreign key.
    """
    user_id = await touch_session(conn, token)
    if user_id is None:
        raise Unauthenticated
    return user_id


Caller = Annotated[int, Depends(caller)]
