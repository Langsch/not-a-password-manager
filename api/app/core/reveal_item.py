"""Revealing the secret fields of an item.

The only place in the system where a password that was already stored leaves the
server. Being signed in is not enough: the account password is asked again, which
is what makes a session safe to leave open for days.

The order below is not a preference. Checking the item first would let a caller
holding only a token learn which ids exist, one 404 at a time — the account
password is verified before the item is looked up so both answers cost the same
information.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg import AsyncConnection

from app.domain.errors import InvalidCredentials, ItemNotFound, Unauthenticated
from app.security.encryption import Cipher
from app.security.passwords import verify_password


class RevealedItem:
    def __init__(self, password: str, notes: str | None) -> None:
        self.password = password
        self.notes = notes


async def reveal_item(
    conn: AsyncConnection[Any],
    cipher: Cipher,
    user_id: int,
    item_id: UUID,
    account_password: str,
) -> RevealedItem:
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
    if not verify_password(account_password, stored_hash):
        raise InvalidCredentials

    sql = """
        SELECT i.password_encrypted,
               i.notes_encrypted
          FROM items i
         WHERE i.external_id = %(item_id)s
           AND i.user_id = %(user_id)s
    """

    params = {
        "item_id": item_id,
        "user_id": user_id,
    }

    async with conn.cursor() as cur:
        await cur.execute(sql, params)
        row = await cur.fetchone()

    # Not there, or not theirs — the caller is told the same thing either way.
    if row is None:
        raise ItemNotFound

    password = cipher.decrypt(row["password_encrypted"])

    notes = None
    if row["notes_encrypted"] is not None:
        notes = cipher.decrypt(row["notes_encrypted"])

    return RevealedItem(password, notes)
