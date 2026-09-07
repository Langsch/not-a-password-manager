"""The failures the API can report, as exceptions this client can branch on.

The server answers every failure with one envelope::

    {"error": {"code": "ITEM_NOT_FOUND", "message": "No such item."}}

``code`` is the contract and never changes its text; ``message`` is written for
a human and must not be interpreted here. So the class is chosen by ``code``
alone, and ``message`` is carried along only to be shown.
"""

from __future__ import annotations

from typing import Any


class ApiError(Exception):
    """A failure the server described with a code from the contract."""

    code: str = "INTERNAL_ERROR"
    message: str = "Something went wrong."

    def __init__(self, message: str | None = None) -> None:
        if message is not None:
            self.message = message

        super().__init__(self.message)


class ValidationError(ApiError):
    code = "VALIDATION_ERROR"
    message = "The request was missing or malformed."


class Unauthenticated(ApiError):
    code = "UNAUTHENTICATED"
    message = "Your session has expired. Sign in again."


class InvalidCredentials(ApiError):
    code = "INVALID_CREDENTIALS"
    message = "Wrong email or password."


class EmailAlreadyRegistered(ApiError):
    code = "EMAIL_ALREADY_REGISTERED"
    message = "That email already has an account."


class ItemNotFound(ApiError):
    code = "ITEM_NOT_FOUND"
    message = "No such item."


class InternalError(ApiError):
    code = "INTERNAL_ERROR"
    message = "The server failed. Check its logs."


class Unreachable(ApiError):
    """No answer at all — wrong address, service down, network gone.

    Not a code from the contract: it never came from the server, because the
    server was never reached.
    """

    code = "UNREACHABLE"
    message = "Could not reach the server."


BY_CODE: dict[str, type[ApiError]] = {
    ValidationError.code: ValidationError,
    Unauthenticated.code: Unauthenticated,
    InvalidCredentials.code: InvalidCredentials,
    EmailAlreadyRegistered.code: EmailAlreadyRegistered,
    ItemNotFound.code: ItemNotFound,
    InternalError.code: InternalError,
}


def from_envelope(body: Any) -> ApiError:
    """Build the exception a failed response describes.

    Anything unrecognised becomes ``InternalError``: a body that is not the
    envelope means we are not talking to this API, or the contract moved. Both
    are the client's problem to report, not to interpret.

    `NOT_FOUND` and `METHOD_NOT_ALLOWED` land here too. They come from the
    framework before a route is reached, so seeing one means this client asked
    for a path or a method that does not exist — a bug here, not a state the
    screen can offer the user a way out of.
    """
    if not isinstance(body, dict):
        return InternalError()

    error = body.get("error")

    if not isinstance(error, dict):
        return InternalError()

    code = error.get("code")
    message = error.get("message")

    if not isinstance(code, str):
        return InternalError()

    if not isinstance(message, str):
        message = None

    failure = BY_CODE.get(code)

    if failure is None:
        return InternalError()

    return failure(message)
