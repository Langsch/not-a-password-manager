"""Shared route dependencies."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg import AsyncConnection

from app.core.sessions import touch_session
from app.domain.errors import Unauthenticated
from app.security.encryption import Cipher

# auto_error=False so a missing header raises our Unauthenticated rather than
# FastAPI's own 403, which would leave through a different shape.
bearer = HTTPBearer(auto_error=False)


async def db(request: Request) -> AsyncIterator[AsyncConnection[Any]]:
    """A connection from the pool, returned to it when the request is done.

    It commits as it goes (see `create_pool`); this dependency no longer owns
    the commit, because its teardown runs after the response has been sent.
    """
    async with request.app.state.pool.connection() as conn:
        yield conn


Db = Annotated[AsyncConnection[Any], Depends(db)]


async def cipher(request: Request) -> Cipher:
    """The process-wide cipher, built once at startup from ENCRYPTION_KEY."""
    built: Cipher = request.app.state.cipher
    return built


Crypto = Annotated[Cipher, Depends(cipher)]


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
