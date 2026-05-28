"""
Global Exception Handlers

Production-grade exception handling:
- Structured responses
- Secure error handling
- Correlation IDs
- Centralized logging
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = structlog.get_logger()


# ---------------------------------------------------------------------
# Base Exception
# ---------------------------------------------------------------------

class SOCException(Exception):
    """
    Base application exception.
    """

    def __init__(
        self,
        detail: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        error_code: str = "SOC_ERROR",
    ):
        self.detail = detail
        self.status_code = status_code
        self.error_code = error_code

        super().__init__(detail)


class DatabaseException(SOCException):

    def __init__(self, detail: str = "Database operation failed"):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="DATABASE_ERROR",
        )


class AuthenticationException(SOCException):

    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="AUTHENTICATION_FAILED",
        )


class PermissionDeniedException(SOCException):

    def __init__(self, detail: str = "Permission denied"):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="PERMISSION_DENIED",
        )


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _request_id(request: Request) -> str:
    """
    Extract or generate request correlation ID.
    """

    return (
        request.headers.get("X-Request-ID")
        or str(uuid.uuid4())
    )


def _json_error(
    *,
    detail: str,
    error_code: str,
    request_id: str,
) -> dict[str, Any]:
    """
    Standardized error response.
    """

    return {
        "success": False,
        "error": {
            "code": error_code,
            "message": detail,
            "request_id": request_id,
        },
    }


# ---------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------

def register_exception_handlers(app: FastAPI) -> None:

    @app.exception_handler(SOCException)
    async def soc_exception_handler(
        request: Request,
        exc: SOCException,
    ):
        request_id = _request_id(request)

        await logger.awarning(
            "soc_exception",
            request_id=request_id,
            path=request.url.path,
            method=request.method,
            status_code=exc.status_code,
            error_code=exc.error_code,
            detail=exc.detail,
        )

        return JSONResponse(
            status_code=exc.status_code,
            content=_json_error(
                detail=exc.detail,
                error_code=exc.error_code,
                request_id=request_id,
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request,
        exc: StarletteHTTPException,
    ):
        request_id = _request_id(request)

        await logger.awarning(
            "http_exception",
            request_id=request_id,
            path=request.url.path,
            method=request.method,
            status_code=exc.status_code,
            detail=str(exc.detail),
        )

        return JSONResponse(
            status_code=exc.status_code,
            content=_json_error(
                detail=str(exc.detail),
                error_code="HTTP_EXCEPTION",
                request_id=request_id,
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ):
        request_id = _request_id(request)

        validation_errors = exc.errors()

        await logger.awarning(
            "validation_error",
            request_id=request_id,
            path=request.url.path,
            method=request.method,
            error_count=len(validation_errors),
        )

        # Avoid leaking schema internals
        sanitized_errors = []

        for err in validation_errors[:10]:
            sanitized_errors.append({
                "field": ".".join(map(str, err.get("loc", []))),
                "message": err.get("msg", "Invalid value"),
            })

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid request payload",
                    "request_id": request_id,
                    "fields": sanitized_errors,
                },
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ):
        request_id = _request_id(request)

        await logger.aerror(
            "unhandled_exception",
            request_id=request_id,
            path=request.url.path,
            method=request.method,
            error=str(exc),
            exc_info=True,
        )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_json_error(
                detail="Internal server error",
                error_code="INTERNAL_SERVER_ERROR",
                request_id=request_id,
            ),
        )