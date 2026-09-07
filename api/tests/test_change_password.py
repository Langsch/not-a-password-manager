"""PUT /account/password."""

from __future__ import annotations

from fastapi.testclient import TestClient

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
LOGOUT = "/api/v1/auth/logout"
PASSWORD = "/api/v1/account/password"

ACCOUNT = {"email": "rafael@example.com", "password": "the old password"}
NEW_PASSWORD = "the new password"


def sign_in(client: TestClient) -> str:
    response = client.post(LOGIN, json=ACCOUNT)
    body = response.json()
    return str(body["token"])


def register_and_sign_in(client: TestClient) -> str:
    client.post(REGISTER, json=ACCOUNT)
    return sign_in(client)


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_the_password_changes(client: TestClient) -> None:
    token = register_and_sign_in(client)

    response = client.put(
        PASSWORD,
        headers=auth(token),
        json={"current_password": ACCOUNT["password"], "new_password": NEW_PASSWORD},
    )

    assert response.status_code == 204

    with_new = client.post(LOGIN, json={**ACCOUNT, "password": NEW_PASSWORD})
    assert with_new.status_code == 200


def test_the_old_password_stops_working(client: TestClient) -> None:
    token = register_and_sign_in(client)

    client.put(
        PASSWORD,
        headers=auth(token),
        json={"current_password": ACCOUNT["password"], "new_password": NEW_PASSWORD},
    )

    with_old = client.post(LOGIN, json=ACCOUNT)
    assert with_old.status_code == 401
    assert with_old.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_the_current_password_is_required_even_with_a_valid_token(client: TestClient) -> None:
    token = register_and_sign_in(client)

    response = client.put(
        PASSWORD,
        headers=auth(token),
        json={"current_password": "not the password", "new_password": NEW_PASSWORD},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"

    still_works = client.post(LOGIN, json=ACCOUNT)
    assert still_works.status_code == 200


def test_without_a_token_it_is_unauthenticated(client: TestClient) -> None:
    client.post(REGISTER, json=ACCOUNT)

    response = client.put(
        PASSWORD,
        json={"current_password": ACCOUNT["password"], "new_password": NEW_PASSWORD},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_a_short_new_password_is_rejected(client: TestClient) -> None:
    token = register_and_sign_in(client)

    response = client.put(
        PASSWORD,
        headers=auth(token),
        json={"current_password": ACCOUNT["password"], "new_password": "short"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_the_callers_own_token_dies_too(client: TestClient) -> None:
    token = register_and_sign_in(client)

    client.put(
        PASSWORD,
        headers=auth(token),
        json={"current_password": ACCOUNT["password"], "new_password": NEW_PASSWORD},
    )

    response = client.post(LOGOUT, headers=auth(token))
    assert response.status_code == 401


def test_a_session_open_somewhere_else_is_dropped(client: TestClient) -> None:
    first = register_and_sign_in(client)
    second = sign_in(client)

    assert first != second

    client.put(
        PASSWORD,
        headers=auth(first),
        json={"current_password": ACCOUNT["password"], "new_password": NEW_PASSWORD},
    )

    response = client.post(LOGOUT, headers=auth(second))
    assert response.status_code == 401


def test_no_session_survives(client: TestClient, sql) -> None:  # type: ignore[no-untyped-def]
    token = register_and_sign_in(client)
    sign_in(client)

    client.put(
        PASSWORD,
        headers=auth(token),
        json={"current_password": ACCOUNT["password"], "new_password": NEW_PASSWORD},
    )

    rows = sql("""
        SELECT count(*)
          FROM sessions s
    """)

    assert rows[0][0] == 0


def test_the_new_password_is_never_stored(client: TestClient, sql) -> None:  # type: ignore[no-untyped-def]
    token = register_and_sign_in(client)

    client.put(
        PASSWORD,
        headers=auth(token),
        json={"current_password": ACCOUNT["password"], "new_password": NEW_PASSWORD},
    )

    rows = sql("""
        SELECT u.password_hash
          FROM users u
    """)

    stored = rows[0][0]
    assert NEW_PASSWORD not in stored
    assert stored.startswith("$argon2id$")
