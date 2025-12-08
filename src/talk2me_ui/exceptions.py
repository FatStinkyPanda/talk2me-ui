"""Custom exception classes for Talk2Me UI API errors.

This module defines custom exceptions for different types of API errors,
providing structured error handling and proper HTTP status codes.
"""

from typing import Any

from fastapi import HTTPException


class Talk2MeException(Exception):
    """Base exception class for Talk2Me UI errors.

    Attributes:
        message: Human-readable error message
        status_code: HTTP status code
        error_code: Machine-readable error code
        details: Additional error details
    """

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(Talk2MeException):
    """Exception raised for input validation errors."""

    def __init__(
        self, message: str, field: str | None = None, details: dict[str, Any] | None = None
    ):
        super().__init__(message, status_code=400, details=details)
        if field:
            self.details["field"] = field


class AuthenticationError(Talk2MeException):
    """Exception raised for authentication failures."""

    def __init__(
        self, message: str = "Authentication required", details: dict[str, Any] | None = None
    ):
        super().__init__(message, status_code=401, details=details)


class AuthorizationError(Talk2MeException):
    """Exception raised for authorization failures."""

    def __init__(
        self, message: str = "Insufficient permissions", details: dict[str, Any] | None = None
    ):
        super().__init__(message, status_code=403, details=details)


class NotFoundError(Talk2MeException):
    """Exception raised when a requested resource is not found."""

    def __init__(
        self, resource: str, resource_id: str | None = None, details: dict[str, Any] | None = None
    ):
        message = f"{resource} not found"
        if resource_id:
            message += f": {resource_id}"
        super().__init__(message, status_code=404, details=details)
        self.details["resource"] = resource
        if resource_id:
            self.details["resource_id"] = resource_id


class ConflictError(Talk2MeException):
    """Exception raised for resource conflicts."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, status_code=409, details=details)


class RateLimitError(Talk2MeException):
    """Exception raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, status_code=429, details=details)
        if retry_after:
            self.details["retry_after"] = retry_after


class ExternalServiceError(Talk2MeException):
    """Exception raised when external service calls fail."""

    def __init__(self, service: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(f"{service} error: {message}", status_code=502, details=details)
        self.details["service"] = service


class ConfigurationError(Talk2MeException):
    """Exception raised for configuration-related errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, status_code=500, details=details)


class FileProcessingError(Talk2MeException):
    """Exception raised for file processing errors."""

    def __init__(
        self, message: str, filename: str | None = None, details: dict[str, Any] | None = None
    ):
        super().__init__(message, status_code=400, details=details)
        if filename:
            self.details["filename"] = filename


class AudioProcessingError(Talk2MeException):
    """Exception raised for audio processing errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, status_code=400, details=details)


def create_http_exception(exc: Talk2MeException) -> HTTPException:
    """Convert a Talk2MeException to a FastAPI HTTPException.

    Args:
        exc: The Talk2MeException to convert

    Returns:
        HTTPException with appropriate status code and details
    """
    return HTTPException(
        status_code=exc.status_code,
        detail={"error": exc.error_code, "message": exc.message, "details": exc.details},
    )


def handle_exception(exc: Exception) -> HTTPException:
    """Handle various exception types and convert to appropriate HTTP responses.

    Args:
        exc: The exception to handle

    Returns:
        HTTPException with appropriate status code and details
    """
    if isinstance(exc, Talk2MeException):
        return create_http_exception(exc)
    elif isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    elif isinstance(exc, FileNotFoundError):
        return HTTPException(status_code=404, detail="File not found")
    elif isinstance(exc, PermissionError):
        return HTTPException(status_code=403, detail="Permission denied")
    else:
        # Generic server error for unexpected exceptions
        return HTTPException(status_code=500, detail="Internal server error")
