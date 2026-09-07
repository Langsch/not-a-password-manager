"""POST /items/{id}/reveal."""

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
    response = client.post(ITEMS, headers=headers, json={"name": "GitHub", **fields})
    return str(response.json()["id"])


def reveal(client: TestClient, headers: dict[str, str], item_id: str, password: str):  # type: ignore[no-untyped-def]
    return client.post(
        f"{ITEMS}/{item_id}/reveal",
        headers=headers,
        json={"password": password},
    )


def test_the_password_comes_back(client: TestClient) -> None:
    headers = sign_in(client, ACCOUNT)
    item_id = add(client, headers, password=SECRET, notes=NOTE)

    response = reveal(client, headers, item_id, ACCOUNT["password"])

    assert response.status_code == 200
    assert response.json() == {"password": SECRET, "notes": NOTE}


def test_an_item_without_notes_reveals_null(client: TestClient) -> None:
    headers = sign_in(client, ACCOUNT)
    item_id = add(client, headers, password=SECRET)

    body = reveal(client, headers, item_id, ACCOUNT["password"]).json()

    assert body == {"password": SECRET, "notes": None}


def test_a_generated_password_reveals_the_same_value(client: TestClient) -> None:
    headers = sign_in(client, ACCOUNT)
    created = client.post(ITEMS, headers=headers, json={"name": "GitHub"}).json()

    body = reveal(client, headers, created["id"], ACCOUNT["password"]).json()

    assert body["password"] == created["password"]


def test_the_wrong_account_password_is_refused(client: TestClient) -> None:
    headers = sign_in(client, ACCOUNT)
    item_id = add(client, headers, password=SECRET)

    response = reveal(client, headers, item_id, "not the password")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_a_wrong_password_hides_whether_the_item_exists(client: TestClient) -> None:
    """The account password is checked first, so a 404 never leaks which ids exist."""
    headers = sign_in(client, ACCOUNT)
    real = add(client, headers, password=SECRET)
    imaginary = str(uuid4())

    on_real = reveal(client, headers, real, "not the password")
    on_imaginary = reveal(client, headers, imaginary, "not the password")

    assert on_real.status_code == on_imaginary.status_code == 401
    assert on_real.json() == on_imaginary.json()


def test_an_unknown_item_is_not_found(client: TestClient) -> None:
    headers = sign_in(client, ACCOUNT)

    response = reveal(client, headers, str(uuid4()), ACCOUNT["password"])

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ITEM_NOT_FOUND"


def test_another_users_item_is_not_found_rather_than_forbidden(client: TestClient) -> None:
    mine = sign_in(client, ACCOUNT)
    theirs = sign_in(client, OTHER)
    not_mine = add(client, theirs, password=SECRET)

    response = reveal(client, mine, not_mine, ACCOUNT["password"])

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ITEM_NOT_FOUND"


def test_without_a_token_it_is_unauthenticated(client: TestClient) -> None:
    headers = sign_in(client, ACCOUNT)
    item_id = add(client, headers, password=SECRET)

    response = client.post(
        f"{ITEMS}/{item_id}/reveal",
        json={"password": ACCOUNT["password"]},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_a_missing_password_field_is_rejected(client: TestClient) -> None:
    headers = sign_in(client, ACCOUNT)
    item_id = add(client, headers, password=SECRET)

    response = client.post(f"{ITEMS}/{item_id}/reveal", headers=headers, json={})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_a_malformed_id_is_rejected(client: TestClient) -> None:
    headers = sign_in(client, ACCOUNT)

    response = reveal(client, headers, "not-a-uuid", ACCOUNT["password"])

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_the_listing_still_carries_no_secret(client: TestClient) -> None:
    headers = sign_in(client, ACCOUNT)
    add(client, headers, password=SECRET, notes=NOTE)

    body = client.get(ITEMS, headers=headers).json()

    assert SECRET not in str(body)
    assert NOTE not in str(body)
