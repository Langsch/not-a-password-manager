"""Opening, validating and closing sessions.

A session dies at whichever comes first: seven days without use, or thirty days
from sign-in. The first deadline is pushed forward on every authenticated
request; the second never moves.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from psycopg import AsyncConnection

from app.security.tokens import new_token, token_digest

IDLE_WINDOW = timedelta(days=7)
ABSOLUTE_LIFETIME = timedelta(days=30)


async def open_session(conn: AsyncConnection[Any], user_id: int) -> tuple[str, datetime]:
    """Returns the token to hand to the client, and when it currently expires."""
    token = new_token()
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO sessions (token_hash, user_id, expires_at, absolute_expires_at)
            VALUES (%s, %s, now() + %s, now() + %s)
            RETURNING expires_at
            """,
            (token_digest(token), user_id, IDLE_WINDOW, ABSOLUTE_LIFETIME),
        )
        row = await cur.fetchone()

    assert row is not None  # noqa: S101 — RETURNING on a successful INSERT
    return token, row["expires_at"]


async def touch_session(conn: AsyncConnection[Any], token: str) -> int | None:
    """The caller's user id, renewing the session — or None if it is not valid.

    LEAST keeps the sliding deadline from overtaking the absolute one, which the
    table's CHECK constraint forbids: near the end of the thirty days a plain
    now() + 7 days would fail the write.
    """
    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE sessions
               SET expires_at = LEAST(now() + %s, absolute_expires_at)
             WHERE token_hash = %s
               AND expires_at > now()
               AND absolute_expires_at > now()
            RETURNING user_id
            """,
            (IDLE_WINDOW, token_digest(token)),
        )
        row = await cur.fetchone()

    if row is None:
        return None

    return int(row["user_id"])


async def close_session(conn: AsyncConnection[Any], token: str) -> None:
    await conn.execute(
        "DELETE FROM sessions WHERE token_hash = %s",
        (token_digest(token),),
    )


async def close_all_sessions(conn: AsyncConnection[Any], user_id: int) -> None:
    await conn.execute(
        "DELETE FROM sessions WHERE user_id = %s",
        (user_id,),
    )
