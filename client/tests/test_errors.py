from __future__ import annotations

import pytest
from napm import errors


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("VALIDATION_ERROR", errors.ValidationError),
        ("UNAUTHENTICATED", errors.Unauthenticated),
        ("INVALID_CREDENTIALS", errors.InvalidCredentials),
        ("EMAIL_ALREADY_REGISTERED", errors.EmailAlreadyRegistered),
        ("ITEM_NOT_FOUND", errors.ItemNotFound),
        ("INTERNAL_ERROR", errors.InternalError),
    ],
)
def test_every_code_in_the_contract_has_a_class(code, expected):
    body = {"error": {"code": code, "message": "whatever"}}

    failure = errors.from_envelope(body)

    assert isinstance(failure, expected)
    assert failure.code == code


def test_the_message_is_carried_not_interpreted():
    body = {"error": {"code": "ITEM_NOT_FOUND", "message": "No such item."}}

    failure = errors.from_envelope(body)

    assert failure.message == "No such item."


@pytest.mark.parametrize(
    "body",
    [
        None,
        "not json at all",
        {},
        {"error": "not a dict"},
        {"error": {"message": "no code"}},
        {"error": {"code": "SOMETHING_NEW", "message": "from a newer server"}},
        {"error": {"code": "NOT_FOUND", "message": "no such path"}},
    ],
)
def test_anything_unreadable_becomes_an_internal_error(body):
    failure = errors.from_envelope(body)

    assert isinstance(failure, errors.InternalError)
