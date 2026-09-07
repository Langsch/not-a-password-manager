"""What lands, and when.

The connection commits as it goes, so a write is durable before the response
leaves — a dependency with ``yield`` is torn down too late for that. The two
operations that need more than one statement to land together carry their own
transaction, and these tests are what keep them from being quietly dropped.
"""

from __future__ import annotations

import os
from typing import Any
from uuid import UUID

import pytest
from app.core import update_item as update_item_module
from app.core.update_item import update_item
from app.db.pool import create_pool
from app.security.encryption import Cipher, decode_key
from fastapi.testclient import TestClient
from psycopg.pq import TransactionStatus

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
ITEMS = "/api/v1/items"
PASSWORD = "/api/v1/account/password"

ACCOUNT = {"email": "rafael@example.com", "password": "the account password"}


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register_and_sign_in(client: TestClient) -> str:
    client.post(REGISTER, json=ACCOUNT)
    response = client.post(LOGIN, json=ACCOUNT)
    return str(response.json()["token"])


def a_cipher() -> Cipher:
    return Cipher(decode_key(os.environ["ENCRYPTION_KEY"]))


async def test_a_pooled_connection_commits_as_it_goes(migrated_database: str) -> None:
    pool = create_pool(migrated_database)
    await pool.open()

    try:
        async with pool.connection() as conn:
            assert conn.autocommit
    finally:
        await pool.close()


async def test_the_locked_read_and_the_write_are_one_transaction(
    client: TestClient,
    aconn,  # type: ignore[no-untyped-def]
    sql,  # type: ignore[no-untyped-def]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FOR UPDATE holds its lock only until the transaction ends.

    `new_password` runs between the locked read and the write, so what it sees
    is what the write will see: a transaction still open, or nothing.
    """
    token = register_and_sign_in(client)
    created = client.post(ITEMS, headers=auth(token), json={"name": "GitHub"})
    item_id = UUID(created.json()["id"])

    rows = sql("""
        SELECT u.id
          FROM users u
    """)
    user_id = int(rows[0][0])

    seen: dict[str, Any] = {}

    def spy() -> str:
        seen["status"] = aconn.info.transaction_status
        return "a password nobody drew"

    monkeypatch.setattr(update_item_module, "new_password", spy)

    await update_item(
        aconn,
        a_cipher(),
        user_id=user_id,
        item_id=item_id,
        changes={},
        generate_password=True,
    )

    assert seen["status"] == TransactionStatus.INTRANS


def test_changing_the_password_leaves_nothing_half_done(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The new password and the dropped sessions are one gesture or neither."""
    token = register_and_sign_in(client)

    def refuse(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("the sessions could not be dropped")

    monkeypatch.setattr("app.core.change_password.close_all_sessions", refuse)

    response = client.put(
        PASSWORD,
        headers=auth(token),
        json={"current_password": ACCOUNT["password"], "new_password": "the new password"},
    )

    assert response.status_code == 500

    with_new = client.post(LOGIN, json={**ACCOUNT, "password": "the new password"})
    assert with_new.status_code == 401

    with_old = client.post(LOGIN, json=ACCOUNT)
    assert with_old.status_code == 200
