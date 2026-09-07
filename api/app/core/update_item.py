"""Changing an item.

The row is read and locked first, then written whole. Building a SET clause out
of whichever fields arrived would mean assembling SQL at runtime; reading first
keeps the statement fixed and makes clearing a field — sending an explicit null —
mean what it says, which COALESCE could not express.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg import AsyncConnection

from app.domain.errors import ItemNotFound
from app.security.encryption import Cipher
from app.security.generator import new_password

UNCHANGED = object()


class UpdatedItem:
    def __init__(self, row: dict[str, Any], generated_password: str | None) -> None:
        self.id = row["id"]
        self.name = row["name"]
        self.username = row["username"]
        self.url = row["url"]
        self.created_at = row["created_at"]
        self.updated_at = row["updated_at"]
        self.generated_password = generated_password


async def update_item(
    conn: AsyncConnection[Any],
    cipher: Cipher,
    user_id: int,
    item_id: UUID,
    changes: dict[str, Any],
    generate_password: bool,
) -> UpdatedItem:
    sql = """
        SELECT i.name,
               i.username,
               i.url,
               i.password_encrypted,
               i.notes_encrypted
          FROM items i
         WHERE i.external_id = %(item_id)s
           AND i.user_id = %(user_id)s
           FOR UPDATE
    """

    params: dict[str, Any] = {
        "item_id": item_id,
        "user_id": user_id,
    }

    # One transaction around the read and the write: the connection is in
    # autocommit, and FOR UPDATE holds its lock only until the transaction
    # ends. Without this the row would be unlocked again before the UPDATE,
    # so a concurrent edit of another field could be lost.
    async with conn.transaction():
        async with conn.cursor() as cur:
            await cur.execute(sql, params)
            current = await cur.fetchone()

        # Not there, or not theirs — the caller is told the same thing either way.
        if current is None:
            raise ItemNotFound

        generated_password = None
        password_encrypted = current["password_encrypted"]

        if generate_password:
            generated_password = new_password()
            password_encrypted = cipher.encrypt(generated_password)
        elif "password" in changes:
            password_encrypted = cipher.encrypt(changes["password"])

        notes_encrypted = current["notes_encrypted"]
        if "notes" in changes:
            notes_encrypted = None
            if changes["notes"] is not None:
                notes_encrypted = cipher.encrypt(changes["notes"])

        sql = """
            UPDATE items i
               SET name = %(name)s,
                   username = %(username)s,
                   url = %(url)s,
                   password_encrypted = %(password_encrypted)s,
                   notes_encrypted = %(notes_encrypted)s
             WHERE i.external_id = %(item_id)s
               AND i.user_id = %(user_id)s
            RETURNING i.external_id AS id,
                      i.name,
                      i.username,
                      i.url,
                      i.created_at,
                      i.updated_at
        """

        params = {
            "name": changes.get("name", current["name"]),
            "username": changes.get("username", current["username"]),
            "url": changes.get("url", current["url"]),
            "password_encrypted": password_encrypted,
            "notes_encrypted": notes_encrypted,
            "item_id": item_id,
            "user_id": user_id,
        }

        async with conn.cursor() as cur:
            await cur.execute(sql, params)
            row = await cur.fetchone()

    assert row is not None  # noqa: S101 — the row was locked a moment ago
    return UpdatedItem(row, generated_password)
