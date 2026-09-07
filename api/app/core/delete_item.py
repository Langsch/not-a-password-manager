"""Removing an item.

It leaves the database for real. There is no trash and no deleted_at column: if
the user said delete, keeping the row would be keeping a liability.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg import AsyncConnection

from app.domain.errors import ItemNotFound


async def delete_item(conn: AsyncConnection[Any], user_id: int, item_id: UUID) -> None:
    sql = """
        DELETE FROM items i
         WHERE i.external_id = %(item_id)s
           AND i.user_id = %(user_id)s
        RETURNING i.id
    """

    params: dict[str, Any] = {
        "item_id": item_id,
        "user_id": user_id,
    }

    async with conn.cursor() as cur:
        await cur.execute(sql, params)
        row = await cur.fetchone()

    # Nothing was removed: it is not there, or it is not theirs.
    if row is None:
        raise ItemNotFound
