from __future__ import annotations

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def error_payload(*, code: str, message: str, details: Any = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
        },
    }
    if details is not None:
        payload["error"]["details"] = details
    return payload


def _status_code_name(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).name
    except ValueError:
        return "UNKNOWN_ERROR"


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        code = f"HTTP_{_status_code_name(exc.status_code)}"
        details = exc.detail if isinstance(exc.detail, list) else None
        message = exc.detail if isinstance(exc.detail, str) else _status_code_name(exc.status_code)
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(code=code, message=message, details=details),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=error_payload(
                code="REQUEST_VALIDATION_ERROR",
                message="Request validation failed",
                details=exc.errors(),
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=error_payload(
                code="INTERNAL_SERVER_ERROR",
                message="Internal server error",
            ),
        )
