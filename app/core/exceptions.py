"""
Custom exception classes and FastAPI exception handlers.
"""
import logging
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exception classes
# ---------------------------------------------------------------------------

class BaseAPIException(HTTPException):
    """Base exception for all API errors."""

    def __init__(
        self,
        status_code: int,
        detail: str,
        headers: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)


class NotFoundError(BaseAPIException):
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class AuthenticationError(BaseAPIException):
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class AuthorizationError(BaseAPIException):
    def __init__(self, detail: str = "Access denied"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class ValidationError(BaseAPIException):
    def __init__(self, detail: str = "Validation failed"):
        super().__init__(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


class ConflictError(BaseAPIException):
    def __init__(self, detail: str = "Resource already exists"):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class DatabaseError(BaseAPIException):
    def __init__(self, detail: str = "Database operation failed"):
        super().__init__(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)


class RateLimitError(BaseAPIException):
    def __init__(self, detail: str = "Rate limit exceeded"):
        super().__init__(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def handle_db_error(error: Exception) -> BaseAPIException:
    """Map database / library errors to appropriate API exceptions."""
    msg = str(error).lower()

    if "unique" in msg or "duplicate" in msg or "already exists" in msg:
        return ConflictError(detail="A record with this value already exists")
    if "not found" in msg or "no result" in msg:
        return NotFoundError(detail=str(error))
    if "auth" in msg or "unauthorized" in msg or "invalid" in msg:
        return AuthenticationError(detail=str(error))
    if "forbidden" in msg:
        return AuthorizationError(detail=str(error))
    if "validation" in msg:
        return ValidationError(detail=str(error))

    return DatabaseError(detail="An unexpected database error occurred")


# ---------------------------------------------------------------------------
# FastAPI exception handlers — call register_exception_handlers(app) at startup
# ---------------------------------------------------------------------------

def register_exception_handlers(app: FastAPI) -> None:
    """Register custom exception handlers on the FastAPI app."""

    @app.exception_handler(BaseAPIException)
    async def api_exception_handler(request: Request, exc: BaseAPIException):
        logger.error(f"API Exception [{exc.status_code}]: {exc.detail}")
        return JSONResponse(
            status_code=exc.status_code,
            content={"status": "error", "message": exc.detail},
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled Exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Internal server error"},
        )
