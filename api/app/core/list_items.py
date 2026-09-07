"""Listing items.

Secret columns are never selected here, so a listing cannot leak one by
accident and no decryption happens on this path.
"""

from __future__ import annotations

from typing import Any

from psycopg import AsyncConnection


class ItemPage:
    def __init__(self, rows: list[dict[str, Any]], total: int) -> None:
        self.rows = rows
        self.total = total


def _escape_for_like(term: str) -> str:
    """A % or _ typed by the user is a character, not a wildcard."""
    escaped = term.replace("\\", "\\\\")
    escaped = escaped.replace("%", "\\%")
    escaped = escaped.replace("_", "\\_")

    return f"%{escaped}%"


async def list_items(
    conn: AsyncConnection[Any],
    user_id: int,
    page: int,
    per_page: int,
    search: str | None,
) -> ItemPage:
    pattern = None
    if search is not None:
        pattern = _escape_for_like(search)

    # The ::text casts are not decoration: used only in IS NULL and ILIKE, the
    # parameter has no type PostgreSQL can infer, and it refuses the query.
    #
    # count(*) OVER () is computed before LIMIT, so it carries the full number of
    # matches without a second round trip. The id in ORDER BY is the tiebreak:
    # without it, two items sharing a name can swap places between pages.
    sql = """
        SELECT i.external_id AS id,
               i.name,
               i.username,
               i.url,
               i.created_at,
               i.updated_at,
               count(*) OVER () AS total
          FROM items i
         WHERE i.user_id = %(user_id)s
           AND (
                 %(pattern)s::text IS NULL
                 OR i.name ILIKE %(pattern)s::text
                 OR i.username ILIKE %(pattern)s::text
               )
         ORDER BY i.name,
                  i.id
         LIMIT %(limit)s
        OFFSET %(offset)s
    """

    params: dict[str, Any] = {
        "user_id": user_id,
        "pattern": pattern,
        "limit": per_page,
        "offset": (page - 1) * per_page,
    }

    async with conn.cursor() as cur:
        await cur.execute(sql, params)
        rows = await cur.fetchall()

    total = 0
    if rows:
        total = int(rows[0]["total"])

    return ItemPage(rows, total)
