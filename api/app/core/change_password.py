"""Changing the account password.

The current password is required even though the caller already holds a valid
token: without it, a stolen token turns into a stolen account.

Every session is dropped, the caller's included. Changing the password is what
someone does when they suspect a stranger is inside, and leaving the other
devices signed in would empty the gesture.
"""

from __future__ import annotations

from typing import Any

from psycopg import AsyncConnection

from app.core.sessions import close_all_sessions
from app.domain.errors import InvalidCredentials, Unauthenticated
from app.security.passwords import hash_password, verify_password


async def change_password(
    conn: AsyncConnection[Any],
    user_id: int,
    current_password: str,
    new_password: str,
) -> None:
    sql = """
        SELECT u.password_hash
          FROM users u
         WHERE u.id = %(user_id)s
    """

    params: dict[str, Any] = {"user_id": user_id}

    async with conn.cursor() as cur:
        await cur.execute(sql, params)
        row = await cur.fetchone()

    # The session pointed at an account that is no longer there.
    if row is None:
        raise Unauthenticated

    stored_hash = row["password_hash"]
    if not verify_password(current_password, stored_hash):
        raise InvalidCredentials

    sql = """
        UPDATE users u
           SET password_hash = %(password_hash)s
         WHERE u.id = %(user_id)s
    """

    params = {
        "password_hash": hash_password(new_password),
        "user_id": user_id,
    }

    await conn.execute(sql, params)
    await close_all_sessions(conn, user_id)
