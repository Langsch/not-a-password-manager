"""POST /items."""

from __future__ import annotations

from fastapi.testclient import TestClient

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
ITEMS = "/api/v1/items"

ACCOUNT = {"email": "rafael@example.com", "password": "a good password"}
SECRET = "K7#mQ2vX!pL9"


def sign_in(client: TestClient) -> dict[str, str]:
    client.post(REGISTER, json=ACCOUNT)
    response = client.post(LOGIN, json=ACCOUNT)
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_creates_an_item(client: TestClient) -> None:
    headers = sign_in(client)

    response = client.post(
        ITEMS,
        headers=headers,
        json={"name": "GitHub", "username": "rafael", "url": "https://github.com"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "GitHub"
    assert body["username"] == "rafael"
    assert body["url"] == "https://github.com"


def test_only_the_name_is_required(client: TestClient) -> None:
    headers = sign_in(client)

    response = client.post(ITEMS, headers=headers, json={"name": "GitHub"})

    assert response.status_code == 201
    assert response.json()["username"] is None


def test_a_missing_name_is_rejected(client: TestClient) -> None:
    headers = sign_in(client)

    response = client.post(ITEMS, headers=headers, json={"username": "rafael"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_without_a_token_it_is_unauthenticated(client: TestClient) -> None:
    response = client.post(ITEMS, json={"name": "GitHub"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_a_password_the_caller_sent_is_not_echoed_back(client: TestClient) -> None:
    headers = sign_in(client)

    response = client.post(ITEMS, headers=headers, json={"name": "GitHub", "password": SECRET})

    assert response.status_code == 201
    assert "password" not in response.json()


def test_leaving_the_password_out_makes_the_server_draw_one(client: TestClient) -> None:
    headers = sign_in(client)

    response = client.post(ITEMS, headers=headers, json={"name": "GitHub"})

    body = response.json()
    assert "password" in body
    assert len(body["password"]) == 20


def test_two_drawn_passwords_differ(client: TestClient) -> None:
    headers = sign_in(client)

    first = client.post(ITEMS, headers=headers, json={"name": "GitHub"}).json()
    second = client.post(ITEMS, headers=headers, json={"name": "GitLab"}).json()

    assert first["password"] != second["password"]


def test_the_password_is_encrypted_in_the_database(client: TestClient, sql) -> None:  # type: ignore[no-untyped-def]
    headers = sign_in(client)
    client.post(ITEMS, headers=headers, json={"name": "GitHub", "password": SECRET})

    rows = sql("""
        SELECT i.password_encrypted
          FROM items i
    """)

    stored = rows[0][0]
    assert SECRET not in stored
    assert stored.startswith("v1.")


def test_the_notes_are_encrypted_too(client: TestClient, sql) -> None:  # type: ignore[no-untyped-def]
    headers = sign_in(client)
    note = "recovery key is in the physical safe"
    client.post(ITEMS, headers=headers, json={"name": "GitHub", "notes": note})

    rows = sql("""
        SELECT i.notes_encrypted
          FROM items i
    """)

    stored = rows[0][0]
    assert note not in stored
    assert stored.startswith("v1.")


def test_the_searchable_columns_stay_readable(client: TestClient, sql) -> None:  # type: ignore[no-untyped-def]
    headers = sign_in(client)
    client.post(
        ITEMS,
        headers=headers,
        json={"name": "GitHub", "username": "rafael", "url": "https://github.com"},
    )

    rows = sql("""
        SELECT i.name,
               i.username,
               i.url
          FROM items i
    """)

    assert rows[0] == ("GitHub", "rafael", "https://github.com")


def test_the_item_belongs_to_the_caller(client: TestClient, sql) -> None:  # type: ignore[no-untyped-def]
    headers = sign_in(client)
    client.post(ITEMS, headers=headers, json={"name": "GitHub"})

    rows = sql("""
        SELECT i.user_id,
               u.email
          FROM items i
          JOIN users u ON u.id = i.user_id
    """)

    assert rows[0][1] == ACCOUNT["email"]
