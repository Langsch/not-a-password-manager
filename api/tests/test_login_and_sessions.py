"""POST /auth/login, POST /auth/logout, and what a token is worth."""

from __future__ import annotations

import time

import pytest
from app.core.sessions import touch_session
from fastapi.testclient import TestClient

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
LOGOUT = "/api/v1/auth/logout"

ACCOUNT = {"email": "rafael@example.com", "password": "a good password"}


def sign_in(client: TestClient) -> str:
    client.post(REGISTER, json=ACCOUNT)
    response = client.post(LOGIN, json=ACCOUNT)
    body = response.json()
    return str(body["token"])


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_login_returns_a_token_and_when_it_expires(client: TestClient) -> None:
    client.post(REGISTER, json=ACCOUNT)

    response = client.post(LOGIN, json=ACCOUNT)

    assert response.status_code == 200
    assert set(response.json()) == {"token", "expires_at"}
    assert response.json()["token"]


def test_a_wrong_password_is_invalid_credentials(client: TestClient) -> None:
    client.post(REGISTER, json=ACCOUNT)

    response = client.post(LOGIN, json={**ACCOUNT, "password": "not the password"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_an_unknown_email_gets_the_same_answer(client: TestClient) -> None:
    response = client.post(LOGIN, json={"email": "nobody@example.com", "password": "whatever!!"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_an_unknown_email_costs_the_same_time_as_a_wrong_password(client: TestClient) -> None:
    """Otherwise the clock says what the error code refuses to."""
    client.post(REGISTER, json=ACCOUNT)

    started = time.monotonic()
    client.post(LOGIN, json={**ACCOUNT, "password": "not the password"})
    wrong_password = time.monotonic() - started

    started = time.monotonic()
    client.post(LOGIN, json={"email": "nobody@example.com", "password": "whatever!!"})
    unknown_email = time.monotonic() - started

    assert unknown_email > wrong_password / 3


def test_the_token_is_never_stored(client: TestClient, sql) -> None:  # type: ignore[no-untyped-def]
    token = sign_in(client)

    rows = sql("SELECT s.token_hash FROM sessions s")

    assert len(rows) == 1
    assert token.encode() not in bytes(rows[0][0])
    assert len(bytes(rows[0][0])) == 32


def test_a_token_reaches_an_authenticated_route(client: TestClient) -> None:
    token = sign_in(client)

    assert client.post(LOGOUT, headers=auth(token)).status_code == 204


def test_no_header_is_unauthenticated(client: TestClient) -> None:
    response = client.post(LOGOUT)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.parametrize("header", [{"Authorization": "Bearer nonsense"}, {"Authorization": "x"}])
def test_a_bad_token_is_unauthenticated(client: TestClient, header: dict[str, str]) -> None:
    sign_in(client)

    response = client.post(LOGOUT, headers=header)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_logout_kills_the_token_immediately(client: TestClient) -> None:
    token = sign_in(client)

    client.post(LOGOUT, headers=auth(token))
    response = client.post(LOGOUT, headers=auth(token))

    assert response.status_code == 401


def test_an_idle_session_expires(client: TestClient, sql) -> None:  # type: ignore[no-untyped-def]
    token = sign_in(client)
    sql("UPDATE sessions s SET expires_at = now() - interval '1 second'")

    assert client.post(LOGOUT, headers=auth(token)).status_code == 401


async def test_a_session_still_dies_at_the_absolute_deadline(
    client: TestClient,
    aconn,
    sql,  # type: ignore[no-untyped-def]
) -> None:
    """Using it every day renews the idle window, never the thirty-day ceiling."""
    token = sign_in(client)
    sql(
        "UPDATE sessions s SET expires_at = now() + interval '30 minutes', "
        "absolute_expires_at = now() + interval '30 minutes'"
    )

    # A renewal now caps at the absolute deadline instead of jumping seven days.
    assert await touch_session(aconn, token) is not None
    capped, absolute = sql("SELECT s.expires_at, s.absolute_expires_at FROM sessions s")[0]
    assert capped == absolute

    sql(
        "UPDATE sessions s SET expires_at = now() - interval '1 second', "
        "absolute_expires_at = now() - interval '1 second'"
    )
    assert await touch_session(aconn, token) is None


async def test_using_the_session_pushes_the_idle_deadline_forward(
    client: TestClient,
    aconn,
    sql,  # type: ignore[no-untyped-def]
) -> None:
    token = sign_in(client)
    sql("UPDATE sessions s SET expires_at = now() + interval '1 hour'")
    before = sql("SELECT s.expires_at FROM sessions s")[0][0]

    assert await touch_session(aconn, token) is not None

    after = sql("SELECT s.expires_at FROM sessions s")[0][0]
    assert after > before


async def test_renewal_never_overtakes_the_absolute_deadline(
    client: TestClient,
    aconn,
    sql,  # type: ignore[no-untyped-def]
) -> None:
    """Near the end of the thirty days a plain now() + 7 days would break the CHECK."""
    token = sign_in(client)
    sql(
        "UPDATE sessions s SET expires_at = now() + interval '30 minutes', "
        "absolute_expires_at = now() + interval '1 hour'"
    )

    assert await touch_session(aconn, token) is not None

    expires, absolute = sql("SELECT s.expires_at, s.absolute_expires_at FROM sessions s")[0]
    assert expires <= absolute
