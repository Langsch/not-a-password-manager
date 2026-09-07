"""PATCH /items/{id} and DELETE /items/{id}."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
ITEMS = "/api/v1/items"

ACCOUNT = {"email": "rafael@example.com", "password": "a good password"}
OTHER = {"email": "someone@example.com", "password": "another password"}

SECRET = "K7#mQ2vX!pL9"
NOTE = "recovery key is in the physical safe"


def sign_in(client: TestClient, account: dict[str, str]) -> dict[str, str]:
    client.post(REGISTER, json=account)
    response = client.post(LOGIN, json=account)
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def add(client: TestClient, headers: dict[str, str], **fields: str) -> str:
    body = {"name": "GitHub", "username": "rafael", "password": SECRET, **fields}
    response = client.post(ITEMS, headers=headers, json=body)
    return str(response.json()["id"])


def reveal(client: TestClient, headers: dict[str, str], item_id: str) -> dict[str, str]:
    response = client.post(
        f"{ITEMS}/{item_id}/reveal",
        headers=headers,
        json={"password": ACCOUNT["password"]},
    )
    return dict(response.json())


# --------------------------------------------------------------------- PATCH


def test_one_field_changes_and_the_rest_stays(client: TestClient) -> None:
    headers = sign_in(client, ACCOUNT)
    item_id = add(client, headers, url="https://github.com")

    response = client.patch(f"{ITEMS}/{item_id}", headers=headers, json={"name": "GitHub Work"})

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "GitHub Work"
    assert body["username"] == "rafael"
    assert body["url"] == "https://github.com"


def test_the_password_can_be_replaced(client: TestClient) -> None:
    headers = sign_in(client, ACCOUNT)
    item_id = add(client, headers)

    client.patch(f"{ITEMS}/{item_id}", headers=headers, json={"password": "the new one"})

    assert reveal(client, headers, item_id)["password"] == "the new one"


def test_a_replaced_password_is_not_echoed_back(client: TestClient) -> None:
    headers = sign_in(client, ACCOUNT)
    item_id = add(client, headers)

    response = client.patch(f"{ITEMS}/{item_id}", headers=headers, json={"password": "the new one"})

    assert "password" not in response.json()


def test_rotating_draws_a_new_password_and_returns_it(client: TestClient) -> None:
    headers = sign_in(client, ACCOUNT)
    item_id = add(client, headers)

    response = client.patch(f"{ITEMS}/{item_id}", headers=headers, json={"generate_password": True})

    body = response.json()
    assert len(body["password"]) == 20
    assert body["password"] != SECRET
    assert reveal(client, headers, item_id)["password"] == body["password"]


def test_notes_can_be_cleared_with_an_explicit_null(client: TestClient) -> None:
    headers = sign_in(client, ACCOUNT)
    item_id = add(client, headers, notes=NOTE)

    client.patch(f"{ITEMS}/{item_id}", headers=headers, json={"notes": None})

    assert reveal(client, headers, item_id)["notes"] is None


def test_leaving_notes_out_does_not_touch_them(client: TestClient) -> None:
    headers = sign_in(client, ACCOUNT)
    item_id = add(client, headers, notes=NOTE)

    client.patch(f"{ITEMS}/{item_id}", headers=headers, json={"name": "GitHub Work"})

    assert reveal(client, headers, item_id)["notes"] == NOTE


def test_the_new_password_is_encrypted_in_the_database(client: TestClient, sql) -> None:  # type: ignore[no-untyped-def]
    headers = sign_in(client, ACCOUNT)
    item_id = add(client, headers)

    client.patch(f"{ITEMS}/{item_id}", headers=headers, json={"password": "the new one"})

    rows = sql("""
        SELECT i.password_encrypted
          FROM items i
    """)

    stored = rows[0][0]
    assert "the new one" not in stored
    assert stored.startswith("v1.")


def test_an_empty_body_is_rejected(client: TestClient) -> None:
    headers = sign_in(client, ACCOUNT)
    item_id = add(client, headers)

    response = client.patch(f"{ITEMS}/{item_id}", headers=headers, json={})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_an_unknown_field_is_rejected(client: TestClient) -> None:
    headers = sign_in(client, ACCOUNT)
    item_id = add(client, headers)

    response = client.patch(f"{ITEMS}/{item_id}", headers=headers, json={"nmae": "typo"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_password_and_generate_password_together_are_rejected(client: TestClient) -> None:
    headers = sign_in(client, ACCOUNT)
    item_id = add(client, headers)

    response = client.patch(
        f"{ITEMS}/{item_id}",
        headers=headers,
        json={"password": "one", "generate_password": True},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_the_name_cannot_be_cleared(client: TestClient) -> None:
    headers = sign_in(client, ACCOUNT)
    item_id = add(client, headers)

    response = client.patch(f"{ITEMS}/{item_id}", headers=headers, json={"name": None})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_patching_an_unknown_item_is_not_found(client: TestClient) -> None:
    headers = sign_in(client, ACCOUNT)

    response = client.patch(f"{ITEMS}/{uuid4()}", headers=headers, json={"name": "x"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ITEM_NOT_FOUND"


def test_patching_without_a_token_is_unauthenticated(client: TestClient) -> None:
    headers = sign_in(client, ACCOUNT)
    item_id = add(client, headers)

    response = client.patch(f"{ITEMS}/{item_id}", json={"name": "x"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


# -------------------------------------------------------------------- DELETE


def test_the_item_is_gone(client: TestClient) -> None:
    headers = sign_in(client, ACCOUNT)
    item_id = add(client, headers)

    response = client.delete(f"{ITEMS}/{item_id}", headers=headers)

    assert response.status_code == 204
    assert response.content == b""
    assert client.get(ITEMS, headers=headers).json()["data"] == []


def test_it_leaves_the_database_for_real(client: TestClient, sql) -> None:  # type: ignore[no-untyped-def]
    headers = sign_in(client, ACCOUNT)
    item_id = add(client, headers)

    client.delete(f"{ITEMS}/{item_id}", headers=headers)

    rows = sql("""
        SELECT count(*)
          FROM items i
    """)

    assert rows[0][0] == 0


def test_deleting_twice_is_not_found(client: TestClient) -> None:
    headers = sign_in(client, ACCOUNT)
    item_id = add(client, headers)

    client.delete(f"{ITEMS}/{item_id}", headers=headers)
    response = client.delete(f"{ITEMS}/{item_id}", headers=headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ITEM_NOT_FOUND"


def test_deleting_without_a_token_is_unauthenticated(client: TestClient) -> None:
    headers = sign_in(client, ACCOUNT)
    item_id = add(client, headers)

    response = client.delete(f"{ITEMS}/{item_id}")

    assert response.status_code == 401


# ------------------------------------------------------- one user, one vault


def test_another_users_item_cannot_be_touched(client: TestClient) -> None:
    """The proof Phase 3 asks for: remove user_id from a query and this fails."""
    mine = sign_in(client, ACCOUNT)
    theirs = sign_in(client, OTHER)
    not_mine = add(client, theirs)

    patched = client.patch(f"{ITEMS}/{not_mine}", headers=mine, json={"name": "mine now"})
    deleted = client.delete(f"{ITEMS}/{not_mine}", headers=mine)

    assert patched.status_code == 404
    assert deleted.status_code == 404

    still_there = client.get(ITEMS, headers=theirs).json()
    assert len(still_there["data"]) == 1
    assert still_there["data"][0]["name"] == "GitHub"
