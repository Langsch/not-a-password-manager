"""Every failure leaves through the envelope, and only through it."""

from __future__ import annotations

import pytest
from app.domain.errors import (
    DomainError,
    EmailAlreadyRegistered,
    InvalidCredentials,
    ItemNotFound,
    Unauthenticated,
)
from app.errors import register_error_handlers
from app.main import app as real_app
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel


class Body(BaseModel):
    name: str


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/raise/{which}")
    async def raise_it(which: str) -> None:
        raise {
            "unauthenticated": Unauthenticated,
            "credentials": InvalidCredentials,
            "email": EmailAlreadyRegistered,
            "item": ItemNotFound,
        }[which]()

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("the password is hunter2")

    @app.post("/body")
    async def body(payload: Body) -> Body:
        return payload

    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize(
    ("which", "status", "code"),
    [
        ("unauthenticated", 401, "UNAUTHENTICATED"),
        ("credentials", 401, "INVALID_CREDENTIALS"),
        ("email", 409, "EMAIL_ALREADY_REGISTERED"),
        ("item", 404, "ITEM_NOT_FOUND"),
    ],
)
def test_domain_errors_map_to_their_code(
    client: TestClient, which: str, status: int, code: str
) -> None:
    response = client.get(f"/raise/{which}")

    assert response.status_code == status
    assert set(response.json()) == {"error"}
    assert response.json()["error"]["code"] == code
    assert response.json()["error"]["message"]


def test_a_malformed_body_is_a_validation_error(client: TestClient) -> None:
    response = client.post("/body", json={})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_an_unhandled_error_says_nothing_about_what_broke(client: TestClient) -> None:
    response = client.get("/boom")

    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "INTERNAL_ERROR", "message": "Something went wrong."}
    }
    assert "hunter2" not in response.text


def test_an_unknown_route_still_uses_the_envelope() -> None:
    with TestClient(real_app) as client:
        response = client.get("/api/v1/nope")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_the_wrong_method_still_uses_the_envelope() -> None:
    with TestClient(real_app) as client:
        response = client.post("/api/v1/health")

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_every_domain_error_declares_a_code_and_a_status() -> None:
    for cls in DomainError.__subclasses__():
        assert cls.code != DomainError.code, cls
        assert 400 <= cls.status < 600, cls
