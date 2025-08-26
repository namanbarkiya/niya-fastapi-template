from fastapi import HTTPException, status
from typing import Any, Dict, Optional


class BaseAPIException(HTTPException):
    """Base exception for API errors"""
    
    def __init__(
        self,
        status_code: int,
        detail: str,
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)


class AuthenticationError(BaseAPIException):
    """Authentication related errors"""
    
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail
        )


class AuthorizationError(BaseAPIException):
    """Authorization related errors"""
    
    def __init__(self, detail: str = "Access denied"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )


class ValidationError(BaseAPIException):
    """Validation related errors"""
    
    def __init__(self, detail: str = "Validation failed"):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail
        )


class DatabaseError(BaseAPIException):
    """Database related errors"""
    
    def __init__(self, detail: str = "Database operation failed"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail
        )


class NotFoundError(BaseAPIException):
    """Resource not found errors"""
    
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail
        )


class RateLimitError(BaseAPIException):
    """Rate limiting errors"""
    
    def __init__(self, detail: str = "Rate limit exceeded"):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail
        )


def handle_supabase_error(error: Exception) -> BaseAPIException:
    """Convert Supabase errors to appropriate API exceptions"""
    error_message = str(error)
    
    if "invalid" in error_message.lower() or "validation" in error_message.lower():
        return ValidationError(detail=error_message)
    elif "not found" in error_message.lower():
        return NotFoundError(detail=error_message)
    elif "auth" in error_message.lower() or "unauthorized" in error_message.lower():
        return AuthenticationError(detail=error_message)
    elif "forbidden" in error_message.lower():
        return AuthorizationError(detail=error_message)
    else:
        return DatabaseError(detail=error_message) 