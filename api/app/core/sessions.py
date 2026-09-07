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
    sql = """
        INSERT INTO sessions AS s (token_hash, user_id, expires_at, absolute_expires_at)
        VALUES (%(token_hash)s, %(user_id)s, now() + %(idle)s, now() + %(absolute)s)
        RETURNING s.expires_at
    """

    token = new_token()
    params: dict[str, Any] = {
        "token_hash": token_digest(token),
        "user_id": user_id,
        "idle": IDLE_WINDOW,
        "absolute": ABSOLUTE_LIFETIME,
    }

    async with conn.cursor() as cur:
        await cur.execute(sql, params)
        row = await cur.fetchone()

    assert row is not None  # noqa: S101 — RETURNING on a successful INSERT
    return token, row["expires_at"]


async def touch_session(conn: AsyncConnection[Any], token: str) -> int | None:
    """The caller's user id, renewing the session — or None if it is not valid.

    LEAST keeps the sliding deadline from overtaking the absolute one, which the
    table's CHECK constraint forbids: near the end of the thirty days a plain
    now() + 7 days would fail the write.
    """
    sql = """
        UPDATE sessions s
           SET expires_at = LEAST(now() + %(idle)s, s.absolute_expires_at)
         WHERE s.token_hash = %(token_hash)s
           AND s.expires_at > now()
           AND s.absolute_expires_at > now()
        RETURNING s.user_id
    """

    params: dict[str, Any] = {
        "idle": IDLE_WINDOW,
        "token_hash": token_digest(token),
    }

    async with conn.cursor() as cur:
        await cur.execute(sql, params)
        row = await cur.fetchone()

    if row is None:
        return None

    return int(row["user_id"])


async def close_session(conn: AsyncConnection[Any], token: str) -> None:
    sql = """
        DELETE FROM sessions s
         WHERE s.token_hash = %(token_hash)s
    """

    params: dict[str, Any] = {"token_hash": token_digest(token)}

    await conn.execute(sql, params)


async def close_all_sessions(conn: AsyncConnection[Any], user_id: int) -> None:
    sql = """
        DELETE FROM sessions s
         WHERE s.user_id = %(user_id)s
    """

    params: dict[str, Any] = {"user_id": user_id}

    await conn.execute(sql, params)
