"""The one envelope every failure leaves through.

    {"error": {"code": "ITEM_NOT_FOUND", "message": "No such item."}}

``code`` is the contract and its text never changes; ``message`` is for humans.
Nothing else may reach the client: an unhandled exception becomes a generic
INTERNAL_ERROR, because the detail of what broke belongs in the log, not in the
response.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.errors import DomainError

log = logging.getLogger(__name__)

# Failures raised by the framework before a route is reached.
TRANSPORT_CODES = {
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
}


def envelope(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain(_: Request, exc: DomainError) -> JSONResponse:
        return envelope(exc.status, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return envelope(422, "VALIDATION_ERROR", "The request body is missing or malformed.")

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = TRANSPORT_CODES.get(exc.status_code, "INTERNAL_ERROR")
        return envelope(exc.status_code, code, str(exc.detail))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        details = {
            "method": request.method,
            "path": request.url.path,
        }
        log.exception("unhandled error on %(method)s %(path)s", details)

        return envelope(500, "INTERNAL_ERROR", "Something went wrong.")
