"""POST /auth/register."""

from __future__ import annotations

from fastapi.testclient import TestClient

ENDPOINT = "/api/v1/auth/register"
GOOD = {"email": "rafael@example.com", "password": "a good password"}


def test_creates_an_account(client: TestClient) -> None:
    response = client.post(ENDPOINT, json=GOOD)

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "email", "created_at"}
    assert body["email"] == GOOD["email"]


def test_does_not_return_a_token(client: TestClient) -> None:
    body = client.post(ENDPOINT, json=GOOD).json()

    assert "token" not in body


def test_the_same_email_twice_is_a_conflict(client: TestClient) -> None:
    client.post(ENDPOINT, json=GOOD)
    response = client.post(ENDPOINT, json=GOOD)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"


def test_the_same_email_in_another_case_is_still_a_conflict(client: TestClient) -> None:
    client.post(ENDPOINT, json=GOOD)
    response = client.post(ENDPOINT, json={**GOOD, "email": "Rafael@Example.com"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"


def test_a_short_password_is_rejected(client: TestClient) -> None:
    response = client.post(ENDPOINT, json={**GOOD, "password": "short"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_a_malformed_email_is_rejected(client: TestClient) -> None:
    response = client.post(ENDPOINT, json={**GOOD, "email": "not-an-email"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_a_missing_field_is_rejected(client: TestClient) -> None:
    response = client.post(ENDPOINT, json={"email": GOOD["email"]})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_the_password_is_never_stored(client: TestClient, sql) -> None:  # type: ignore[no-untyped-def]
    client.post(ENDPOINT, json=GOOD)

    rows = sql("SELECT u.email, u.password_hash FROM users u")

    assert len(rows) == 1
    stored = rows[0][1]
    assert GOOD["password"] not in stored
    assert stored.startswith("$argon2id$")


def test_the_id_is_the_public_uuid_not_the_row_id(client: TestClient, sql) -> None:  # type: ignore[no-untyped-def]
    body = client.post(ENDPOINT, json=GOOD).json()

    rows = sql("SELECT u.id, u.external_id::text FROM users u")

    assert rows[0][0] == 1
    assert body["id"] == rows[0][1]
    assert body["id"] != "1"
