"""Consistent API error responses in the form ``{code, message}``."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from pymongo.errors import PyMongoError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class ErrorResponse(BaseModel):
    """Machine-readable error code and human-readable English message."""

    code: str = Field(description="Stable machine-readable error code.")
    message: str = Field(description="Human-readable English error message.")


class ApiError(Exception):
    """Domain error returned to clients as ``{code, message}``."""

    def __init__(self, status: int, code: str, message: str) -> None:
        self.status = status
        self.code = code
        self.message = message


def not_found() -> ApiError:
    return ApiError(404, "NOT_FOUND", "The object was not found or access is denied.")


def conflict(message: str = "The state changed. Reload it before saving again.") -> ApiError:
    return ApiError(409, "CONFLICT", message)


def register_error_handlers(app: FastAPI) -> None:
    """Register handlers that convert exceptions into consistent JSON errors."""

    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse({"code": exc.code, "message": exc.message}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Validation details may include submitted data and are intentionally omitted.
        return JSONResponse(
            {"code": "VALIDATION_ERROR", "message": "Invalid fields or JSON structure."},
            status_code=422,
        )

    @app.exception_handler(HTTPException)
    async def handle_http(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            {"code": "HTTP_ERROR", "message": str(exc.detail)}, status_code=exc.status_code
        )

    @app.exception_handler(PyMongoError)
    async def handle_mongo(request: Request, exc: PyMongoError) -> JSONResponse:
        logger.error("Database error: %s", exc)
        return JSONResponse(
            {"code": "DATABASE_UNAVAILABLE", "message": "The database is unavailable."},
            status_code=503,
        )
