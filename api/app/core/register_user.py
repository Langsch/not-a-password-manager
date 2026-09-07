"""Creating an account.

The password is hashed here and never stored, not even encrypted: nothing in
the system needs to read it back.
"""

from __future__ import annotations

from typing import Any

from psycopg import AsyncConnection, errors

from app.domain.errors import EmailAlreadyRegistered
from app.security.passwords import hash_password


async def register_user(conn: AsyncConnection[Any], email: str, password: str) -> dict[str, Any]:
    sql = """
        INSERT INTO users AS u (email, password_hash)
        VALUES (%(email)s, %(password_hash)s)
        RETURNING u.external_id AS id,
                  u.email,
                  u.created_at
    """

    params = {
        "email": email,
        "password_hash": hash_password(password),
    }

    try:
        async with conn.cursor() as cur:
            await cur.execute(sql, params)
            row = await cur.fetchone()
    except errors.UniqueViolation as exc:
        raise EmailAlreadyRegistered from exc

    assert row is not None  # noqa: S101 — RETURNING on a successful INSERT

    return {
        "id": row["id"],
        "email": row["email"],
        "created_at": row["created_at"],
    }
