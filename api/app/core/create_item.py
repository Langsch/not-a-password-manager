"""Storing an item.

The password and the notes are encrypted here; the name, username and url are
not, which is what lets the listing search and sort in SQL.
"""

from __future__ import annotations

from typing import Any

from psycopg import AsyncConnection

from app.security.encryption import Cipher
from app.security.generator import new_password


class StoredItem:
    """The stored item, plus the password when the server drew it.

    A drawn password comes back once, here, because the caller has no other way
    to learn what it is. One they sent themselves is not echoed.
    """

    def __init__(self, row: dict[str, Any], generated_password: str | None) -> None:
        self.id = row["id"]
        self.name = row["name"]
        self.username = row["username"]
        self.url = row["url"]
        self.created_at = row["created_at"]
        self.updated_at = row["updated_at"]
        self.generated_password = generated_password


async def create_item(
    conn: AsyncConnection[Any],
    cipher: Cipher,
    user_id: int,
    name: str,
    username: str | None,
    url: str | None,
    password: str | None,
    notes: str | None,
) -> StoredItem:
    generated_password = None
    if password is None:
        generated_password = new_password()
        password = generated_password

    notes_encrypted = None
    if notes is not None:
        notes_encrypted = cipher.encrypt(notes)

    sql = """
        INSERT INTO items AS i (user_id, name, username, url, password_encrypted, notes_encrypted)
        VALUES (
            %(user_id)s,
            %(name)s,
            %(username)s,
            %(url)s,
            %(password_encrypted)s,
            %(notes_encrypted)s
        )
        RETURNING i.external_id AS id,
                  i.name,
                  i.username,
                  i.url,
                  i.created_at,
                  i.updated_at
    """

    params: dict[str, Any] = {
        "user_id": user_id,
        "name": name,
        "username": username,
        "url": url,
        "password_encrypted": cipher.encrypt(password),
        "notes_encrypted": notes_encrypted,
    }

    async with conn.cursor() as cur:
        await cur.execute(sql, params)
        row = await cur.fetchone()

    assert row is not None  # noqa: S101 — RETURNING on a successful INSERT
    return StoredItem(row, generated_password)
