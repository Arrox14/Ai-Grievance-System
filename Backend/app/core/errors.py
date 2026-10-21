import logging
import sqlite3

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


logger = logging.getLogger("app.errors")


def _error_code(status_code: int) -> str:
    return {
        400: "bad_request",
        401: "authentication_required",
        403: "permission_denied",
        404: "not_found",
        409: "conflict",
        413: "payload_too_large",
        422: "validation_error",
    }.get(status_code, "request_failed")


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException):
        detail = exc.detail
        if isinstance(detail, (dict, list)):
            message = "Request failed"
            safe_detail = message
        else:
            message = str(detail)
            safe_detail = detail
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content={
                "detail": safe_detail,
                "code": _error_code(exc.status_code),
                "message": message,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        safe_errors = [
            {
                "location": list(error.get("loc", ())),
                "message": error.get("msg", "Invalid value"),
                "type": error.get("type", "value_error"),
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Request validation failed",
                "code": "validation_error",
                "message": "Request validation failed",
                "errors": safe_errors,
            },
        )

    @app.exception_handler(sqlite3.Error)
    async def handle_database_error(request: Request, exc: sqlite3.Error):
        logger.exception("Database operation failed")
        return JSONResponse(
            status_code=500,
            content={
                "detail": "An internal server error occurred",
                "code": "internal_server_error",
                "message": "An internal server error occurred",
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        logger.exception("Unhandled request error")
        return JSONResponse(
            status_code=500,
            content={
                "detail": "An internal server error occurred",
                "code": "internal_server_error",
                "message": "An internal server error occurred",
            },
        )
