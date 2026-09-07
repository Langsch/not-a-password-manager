"""Signing in."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from psycopg import AsyncConnection

from app.core.sessions import open_session
from app.domain.errors import InvalidCredentials
from app.security.passwords import verify_password, waste_time


async def login_user(conn: AsyncConnection[Any], email: str, password: str) -> tuple[str, datetime]:
    sql = """
        SELECT id, password_hash
          FROM users
         WHERE lower(email) = lower(%(email)s)
    """

    params = {"email": email}

    async with conn.cursor() as cur:
        await cur.execute(sql, params)
        row = await cur.fetchone()

    # No account still costs a verification. Without this, the response time
    # tells a stranger which emails are registered — the same thing separate
    # error codes would tell them.
    if row is None:
        waste_time()
        raise InvalidCredentials

    if not verify_password(password, row["password_hash"]):
        raise InvalidCredentials

    return await open_session(conn, int(row["id"]))
