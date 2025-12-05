"""
Input validation decorators and middleware for Talk2Me UI.

This module provides validation decorators and middleware for securing API endpoints
and ensuring data integrity.
"""

import functools
import re
from collections.abc import Callable

from fastapi import Request

from .config import get_config
from .exceptions import ValidationError


class ValidationMiddleware:
    """
    Middleware for input validation and security checks.

    Provides rate limiting, input sanitization, and security validations.
    """

    def __init__(self):
        self.config = get_config()
        # Simple in-memory rate limiting (in production, use Redis/external service)
        self.request_counts: dict[str, list[float]] = {}
        self.max_requests_per_minute = 60  # Configurable

    async def validate_request(self, request: Request) -> None:
        """
        Validate incoming request for security and rate limiting.

        Args:
            request: FastAPI request object

        Raises:
            ValidationError: If validation fails
            RateLimitError: If rate limit exceeded
        """
        # Get client identifier (IP address for now)
        client_ip = self._get_client_ip(request)

        # Check rate limit
        await self._check_rate_limit(client_ip)

        # Validate request size
        await self._validate_request_size(request)

        # Sanitize headers
        self._validate_headers(request)

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Check for forwarded headers first
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        # Fall back to direct connection
        return request.client.host if request.client else "unknown"

    async def _check_rate_limit(self, client_ip: str) -> None:
        """Check if client has exceeded rate limit."""
        import time

        from .exceptions import RateLimitError

        current_time = time.time()
        window_start = current_time - 60  # 1 minute window

        # Clean old entries
        if client_ip in self.request_counts:
            self.request_counts[client_ip] = [
                ts for ts in self.request_counts[client_ip] if ts > window_start
            ]
        else:
            self.request_counts[client_ip] = []

        # Check current count
        if len(self.request_counts[client_ip]) >= self.max_requests_per_minute:
            raise RateLimitError(
                "Rate limit exceeded",
                retry_after=int(60 - (current_time - self.request_counts[client_ip][0])),
            )

        # Add current request
        self.request_counts[client_ip].append(current_time)

    async def _validate_request_size(self, request: Request) -> None:
        """Validate request body size."""
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                max_size = 10 * 1024 * 1024  # 10MB default
                if size > max_size:
                    raise ValidationError(
                        f"Request too large: {size} bytes. Maximum allowed: {max_size} bytes",
                        details={"request_size": size, "max_size": max_size},
                    )
            except ValueError:
                pass  # Invalid content-length header, let FastAPI handle it

    def _validate_headers(self, request: Request) -> None:
        """Validate and sanitize request headers."""
        # Check for suspicious headers
        suspicious_patterns = [
            r"<script",
            r"javascript:",
            r"on\w+\s*=",
            r"vbscript:",
            r"data:",
            r"mozilla",
        ]

        for header_name, header_value in request.headers.items():
            for pattern in suspicious_patterns:
                if re.search(pattern, header_value, re.IGNORECASE):
                    raise ValidationError(
                        f"Suspicious content detected in header {header_name}",
                        details={"header": header_name},
                    )


def validate_text_input(
    min_length: int | None = None,
    max_length: int | None = None,
    allowed_chars: str | None = None,
    disallow_html: bool = True,
) -> Callable:
    """
    Decorator for validating text input parameters.

    Args:
        min_length: Minimum allowed length
        max_length: Maximum allowed length
        allowed_chars: Regex pattern for allowed characters
        disallow_html: Whether to disallow HTML tags

    Returns:
        Validation decorator
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract text parameters from request
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

            if request:
                # Validate form data
                form_data = await request.form()
                for field_name, field_value in form_data.items():
                    if isinstance(field_value, str):
                        _validate_text_field(
                            field_name,
                            field_value,
                            min_length,
                            max_length,
                            allowed_chars,
                            disallow_html,
                        )

            # Validate keyword arguments
            for key, value in kwargs.items():
                if isinstance(value, str):
                    _validate_text_field(
                        key, value, min_length, max_length, allowed_chars, disallow_html
                    )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def _validate_text_field(
    field_name: str,
    value: str,
    min_length: int | None,
    max_length: int | None,
    allowed_chars: str | None,
    disallow_html: bool,
) -> None:
    """Validate a single text field."""
    # Check length
    if min_length and len(value) < min_length:
        raise ValidationError(
            f"Field '{field_name}' too short. Minimum length: {min_length}",
            field=field_name,
            details={"min_length": min_length, "actual_length": len(value)},
        )

    if max_length and len(value) > max_length:
        raise ValidationError(
            f"Field '{field_name}' too long. Maximum length: {max_length}",
            field=field_name,
            details={"max_length": max_length, "actual_length": len(value)},
        )

    # Check allowed characters
    if allowed_chars and not re.match(f"^[{allowed_chars}]*$", value):
        raise ValidationError(
            f"Field '{field_name}' contains invalid characters",
            field=field_name,
            details={"allowed_pattern": allowed_chars},
        )

    # Check for HTML
    if disallow_html and re.search(r"<[^>]+>", value):
        raise ValidationError(
            f"Field '{field_name}' contains HTML tags which are not allowed", field=field_name
        )


def validate_file_upload(
    allowed_extensions: list[str] | None = None,
    max_size: int | None = None,
    allowed_mime_types: list[str] | None = None,
) -> Callable:
    """
    Decorator for validating file upload parameters.

    Args:
        allowed_extensions: List of allowed file extensions
        max_size: Maximum file size in bytes
        allowed_mime_types: List of allowed MIME types

    Returns:
        Validation decorator
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            from fastapi import UploadFile

            # Find UploadFile parameters
            for key, value in kwargs.items():
                if isinstance(value, UploadFile):
                    _validate_uploaded_file(
                        key, value, allowed_extensions, max_size, allowed_mime_types
                    )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def _validate_uploaded_file(
    field_name: str,
    file: "UploadFile",
    allowed_extensions: list[str] | None,
    max_size: int | None,
    allowed_mime_types: list[str] | None,
) -> None:
    """Validate an uploaded file."""
    # Check file extension
    if allowed_extensions:
        from pathlib import Path

        ext = Path(file.filename).suffix.lower()
        if ext not in [e.lower() for e in allowed_extensions]:
            raise ValidationError(
                f"File type not allowed. Allowed extensions: {', '.join(allowed_extensions)}",
                field=field_name,
                details={"allowed_extensions": allowed_extensions, "provided_extension": ext},
            )

    # Check MIME type
    if allowed_mime_types and file.content_type not in allowed_mime_types:
        raise ValidationError(
            f"File type not allowed. Allowed MIME types: {', '.join(allowed_mime_types)}",
            field=field_name,
            details={
                "allowed_mime_types": allowed_mime_types,
                "provided_mime_type": file.content_type,
            },
        )

    # Check file size
    if max_size:
        file.file.seek(0, 2)  # Seek to end
        size = file.file.tell()
        file.file.seek(0)  # Reset to beginning

        if size > max_size:
            raise ValidationError(
                f"File too large. Maximum size: {max_size} bytes",
                field=field_name,
                details={"max_size": max_size, "actual_size": size},
            )


class InputSanitizer:
    """Utility class for sanitizing user inputs."""

    @staticmethod
    def sanitize_text(text: str) -> str:
        """Sanitize text input by removing potentially dangerous content."""
        if not text:
            return text

        # Remove null bytes
        text = text.replace("\x00", "")

        # Remove control characters except newlines and tabs
        text = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

        return text

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename to prevent path traversal and other issues."""
        if not filename:
            return filename

        # Remove path separators
        filename = re.sub(r"[\/\\]", "", filename)

        # Remove control characters
        filename = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", filename)

        # Limit length
        if len(filename) > 255:
            name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
            if ext:
                filename = name[:250] + "." + ext
            else:
                filename = filename[:255]

        return filename


# Global validation middleware instance
validation_middleware = ValidationMiddleware()
