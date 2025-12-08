"""Input validation decorators and middleware for Talk2Me UI.

This module provides validation decorators and middleware for securing API endpoints
and ensuring data integrity. Also includes environment variable validation.
"""

import functools
import logging
import os
import re
from collections.abc import Callable
from typing import Any, cast

from fastapi import Request, UploadFile

from .config import get_config
from .exceptions import ValidationError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ValidationMiddleware:
    """Middleware for input validation and security checks.

    Provides rate limiting, input sanitization, and security validations.
    """

    def __init__(self):
        self.config = get_config()
        # Simple in-memory rate limiting (in production, use Redis/external service)
        self.request_counts: dict[str, list[float]] = {}
        self.max_requests_per_minute = 60  # Configurable

    async def validate_request(self, request: Request) -> None:
        """Validate incoming request for security and rate limiting.

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
        if forwarded := request.headers.get("X-Forwarded-For"):
            return str(forwarded).split(",")[0].strip()

        # Fall back to direct connection
        if request.client:
            host = cast(str, request.client.host or "unknown")
            return host

        return "unknown"

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
            r"expression\s*\(",
            r"eval\s*\(",
            r"document\.cookie",
            r"document\.location",
            r"window\.location",
            r"innerHTML",
            r"outerHTML",
        ]

        # Check for dangerous header values
        for header_name, header_value in request.headers.items():
            # Skip validation for known safe headers
            if header_name.lower() in [
                "user-agent",
                "accept",
                "accept-encoding",
                "accept-language",
            ]:
                continue

            for pattern in suspicious_patterns:
                if re.search(pattern, header_value, re.IGNORECASE):
                    raise ValidationError(
                        f"Suspicious content detected in header {header_name}",
                        details={"header": header_name},
                    )

        # Additional header security checks
        self._check_header_security(request)

    def _check_header_security(self, request: Request) -> None:  # pragma: noqa C901
        """Perform additional header security checks."""
        # Check for path traversal in headers
        path_headers = ["referer", "origin"]
        for header_name in path_headers:
            header_value = request.headers.get(header_name)
            if (
                header_value
                and (".." in header_value or "//" in header_value)
                and ("../" in header_value or "..\\" in header_value)
            ):
                raise ValidationError(
                    f"Potential path traversal detected in {header_name} header",
                    details={"header": header_name},
                )

        # Check User-Agent for suspicious patterns
        user_agent = request.headers.get("User-Agent", "")
        if user_agent:
            # Check for SQL injection patterns in User-Agent
            sql_patterns = [
                r"(\%27)|(\')|(\-\-)|(\%23)|(#)",
                r"(\%22)|(\")",
                r"((\%3D)|(=))[^\n]*((\%27)|(\')|(\-\-)|(\%3B)|(;))",
            ]
            for pattern in sql_patterns:
                if re.search(pattern, user_agent, re.IGNORECASE):
                    raise ValidationError(
                        "Suspicious User-Agent header detected",
                        details={"user_agent": user_agent[:100]},  # Truncate for security
                    )

        # Check for oversized headers
        for header_name, header_value in request.headers.items():
            if len(header_value) > 4096:  # 4KB limit per header
                raise ValidationError(
                    f"Header {header_name} is too large",
                    details={"header": header_name, "size": len(header_value)},
                )


def validate_text_input(
    min_length: int | None = None,
    max_length: int | None = None,
    allowed_chars: str | None = None,
    disallow_html: bool = True,
) -> Callable:
    """Decorator for validating text input parameters.

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
    """Decorator for validating file upload parameters.

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
    file: UploadFile,
    allowed_extensions: list[str] | None,
    max_size: int | None,
    allowed_mime_types: list[str] | None,
) -> None:
    """Validate an uploaded file."""
    # Check file extension
    if allowed_extensions:
        from pathlib import Path

        ext = Path(file.filename or "").suffix.lower()
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

        # Remove path separators and dangerous characters
        filename = re.sub(r"[\/\\]", "", filename)
        filename = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", filename)

        # Remove additional dangerous characters
        filename = re.sub(r"[<>|:\"*?]", "", filename)

        # Prevent directory traversal
        filename = re.sub(r"\.\.", "", filename)

        # Limit length
        if len(filename) > 255:
            name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
            filename = name[:250] + "." + ext if ext else filename[:255]

        return filename

    @staticmethod
    def sanitize_url(url: str) -> str:
        """Sanitize URL to prevent malicious redirects and injection."""
        if not url:
            return url

        # Remove null bytes and control characters
        url = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", url)

        # Prevent javascript: protocol
        if url.lower().startswith("javascript:"):
            return ""

        # Prevent data: protocol (unless specifically allowed)
        if url.lower().startswith("data:"):
            return ""

        # Basic XSS prevention in URLs
        url = re.sub(r"<[^>]+>", "", url)

        return url

    @staticmethod
    def validate_file_content(file_content: bytes) -> bool:
        """Validate file content for security issues.

        Args:
            file_content: Raw file content as bytes

        Returns:
            True if content is safe, False otherwise
        """
        # Check for embedded scripts in text-based files
        try:
            text_content = file_content.decode("utf-8", errors="ignore")
            dangerous_patterns = [
                r"<script[^>]*>.*?</script>",
                r"javascript:",
                r"vbscript:",
                r"on\w+\s*=",
                r"eval\s*\(",
                r"document\.cookie",
                r"document\.location",
            ]

            for pattern in dangerous_patterns:
                if re.search(pattern, text_content, re.IGNORECASE | re.DOTALL):
                    return False
        except UnicodeDecodeError:
            # Binary file, skip text-based checks
            pass

        # Check for magic bytes that indicate dangerous file types
        if file_content.startswith(b"\x4d\x5a"):  # MZ header (Windows executable)
            return False
        if file_content.startswith(b"\x7f\x45\x4c\x46"):  # ELF header (Linux executable)
            return False

        return not file_content.startswith(b"\x23\x21")  # Shebang (script file)


class EnvironmentValidator:
    """Validator for environment variables with comprehensive checks."""

    # Required environment variables by environment
    REQUIRED_VARS = {
        "development": ["APP_ENV", "LOG_LEVEL", "DEBUG", "HOST", "PORT", "WORKERS"],
        "production": [
            "APP_ENV",
            "LOG_LEVEL",
            "DEBUG",
            "HOST",
            "PORT",
            "WORKERS",
            "SECRET_KEY",
            "SESSION_SECRET",
        ],
    }

    # Optional but recommended variables
    RECOMMENDED_VARS = [
        "ALLOWED_HOSTS",
        "MAX_FILE_SIZE",
        "UPLOAD_DIR",
        "CORS_ORIGINS",
        "ENABLE_METRICS",
        "METRICS_PORT",
    ]

    # Security-sensitive variables that should not have default values
    SECURITY_VARS = ["SECRET_KEY", "SESSION_SECRET", "TALK2ME_API_KEY"]

    @classmethod
    def validate_environment(cls) -> list[str]:
        """Validate all environment variables and return list of issues.

        Returns:
            List of validation error messages
        """
        issues = []

        # Get current environment
        app_env = os.getenv("APP_ENV", "development").lower()

        # Check required variables
        required = cls.REQUIRED_VARS.get(app_env, cls.REQUIRED_VARS["development"])
        for var in required:
            if not os.getenv(var):
                issues.append(f"Required variable '{var}' is not set")

        # Check security variables
        for var in cls.SECURITY_VARS:
            value = os.getenv(var)
            if value:
                cls._validate_security_var(var, value, issues)

        # Validate specific variables
        cls._validate_app_env(app_env, issues)
        cls._validate_log_level(os.getenv("LOG_LEVEL"), issues)
        cls._validate_debug(os.getenv("DEBUG"), issues)
        cls._validate_port(os.getenv("PORT"), issues)
        cls._validate_workers(os.getenv("WORKERS"), issues)
        cls._validate_max_file_size(os.getenv("MAX_FILE_SIZE"), issues)
        cls._validate_boolean_vars(issues)
        cls._validate_paths(issues)

        return issues

    @classmethod
    def _validate_security_var(cls, var: str, value: str, issues: list[str]) -> None:
        """Validate security-sensitive variables."""
        app_env = os.getenv("APP_ENV", "development").lower()
        if var in ["SECRET_KEY", "SESSION_SECRET"]:
            if app_env == "production" and len(value) < 32:
                issues.append(f"Security variable '{var}' should be at least 32 characters long")
            if value in [
                "your-secure-random-secret-key-here",
                "your-secure-random-session-secret-here",
                "dev-secret-key-change-in-production",
                "dev-session-secret",
                "change-this-to-a-secure-random-key-in-production",
                "change-this-to-a-secure-random-session-key",
            ]:
                issues.append(
                    f"Security variable '{var}' contains default/placeholder value - change immediately"
                )

    @classmethod
    def _validate_app_env(cls, app_env: str, issues: list[str]) -> None:
        """Validate APP_ENV variable."""
        valid_envs = ["development", "production", "staging", "test"]
        if app_env not in valid_envs:
            issues.append(
                f"APP_ENV '{app_env}' is not valid. Must be one of: {', '.join(valid_envs)}"
            )

    @classmethod
    def _validate_log_level(cls, log_level: str | None, issues: list[str]) -> None:
        """Validate LOG_LEVEL variable."""
        if log_level:
            valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            if log_level.upper() not in valid_levels:
                issues.append(
                    f"LOG_LEVEL '{log_level}' is not valid. Must be one of: {', '.join(valid_levels)}"
                )

    @classmethod
    def _validate_debug(cls, debug: str | None, issues: list[str]) -> None:
        """Validate DEBUG variable."""
        if debug:
            if debug.lower() not in ["true", "false"]:
                issues.append("DEBUG must be 'true' or 'false'")
            elif debug.lower() == "true":
                app_env = os.getenv("APP_ENV", "development").lower()
                if app_env == "production":
                    issues.append("DEBUG should be 'false' in production environment")

    @classmethod
    def _validate_port(cls, port: str | None, issues: list[str]) -> None:
        """Validate PORT variable."""
        if port:
            try:
                port_num = int(port)
                if not (1 <= port_num <= 65535):
                    issues.append("PORT must be between 1 and 65535")
            except ValueError:
                issues.append("PORT must be a valid integer")

    @classmethod
    def _validate_workers(cls, workers: str | None, issues: list[str]) -> None:
        """Validate WORKERS variable."""
        if workers:
            try:
                workers_num = int(workers)
                if workers_num < 1:
                    issues.append("WORKERS must be at least 1")
                elif workers_num > 100:
                    issues.append("WORKERS seems too high (>100), verify this is intentional")
            except ValueError:
                issues.append("WORKERS must be a valid integer")

    @classmethod
    def _validate_max_file_size(cls, max_file_size: str | None, issues: list[str]) -> None:
        """Validate MAX_FILE_SIZE variable."""
        if max_file_size:
            try:
                size = int(max_file_size)
                if size <= 0:
                    issues.append("MAX_FILE_SIZE must be greater than 0")
                # Warn about very large file sizes
                if size > 100 * 1024 * 1024:  # 100MB
                    issues.append(
                        "MAX_FILE_SIZE is very large (>100MB), consider security implications"
                    )
            except ValueError:
                issues.append("MAX_FILE_SIZE must be a valid integer")

    @classmethod
    def _validate_boolean_vars(cls, issues: list[str]) -> None:
        """Validate boolean environment variables."""
        boolean_vars = ["ENABLE_METRICS"]
        for var in boolean_vars:
            value = os.getenv(var)
            if value and value.lower() not in ["true", "false"]:
                issues.append(f"{var} must be 'true' or 'false'")

    @classmethod
    def _validate_paths(cls, issues: list[str]) -> None:
        """Validate path-related environment variables."""
        path_vars = {
            "SSL_CERT_PATH": "SSL certificate file",
            "SSL_KEY_PATH": "SSL private key file",
            "LOG_FILE": "log file",
        }

        for var, description in path_vars.items():
            path = os.getenv(var)
            if path and not os.path.isabs(path):
                issues.append(f"{var} should be an absolute path for {description}")

    @classmethod
    def get_validation_summary(cls) -> dict[str, Any]:
        """Get a summary of environment validation results.

        Returns:
            Dictionary with validation results
        """
        issues = cls.validate_environment()
        app_env = os.getenv("APP_ENV", "development").lower()

        return {
            "environment": app_env,
            "total_issues": len(issues),
            "issues": issues,
            "is_valid": len(issues) == 0,
            "required_vars_present": all(
                os.getenv(var) for var in cls.REQUIRED_VARS.get(app_env, [])
            ),
        }


def validate_environment_on_startup() -> None:
    """Validate environment variables at application startup.

    Raises:
        ValueError: If critical environment validation fails
    """
    summary = EnvironmentValidator.get_validation_summary()

    if summary["issues"]:
        logger.info("🔍 Environment Validation Results:")
        logger.info(f"Environment: {summary['environment']}")
        logger.info(f"Issues found: {summary['total_issues']}")

        for issue in summary["issues"]:
            logger.warning(f"  ⚠️  {issue}")

        # Check for critical issues
        critical_issues = [
            issue
            for issue in summary["issues"]
            if "Required variable" in issue or "Security variable" in issue
        ]
        if critical_issues:
            logger.error("\n❌ Critical environment issues found. Please fix before proceeding.")
            raise ValueError("Critical environment configuration issues detected")

        logger.info(
            "\n✅ Non-critical issues found. Application will continue but consider fixing them."
        )


# Global validation middleware instance
validation_middleware = ValidationMiddleware()
