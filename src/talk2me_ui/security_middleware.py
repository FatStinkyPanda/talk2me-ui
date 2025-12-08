"""Security middleware for Talk2Me UI.

This module provides additional security middleware for protecting
against common web vulnerabilities and implementing security best practices.
"""

import logging
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class SecurityMiddleware(BaseHTTPMiddleware):
    """Additional security middleware for best practices."""

    def __init__(self, app, allowed_hosts: Optional[list[str]] = None):
        """Initialize security middleware.

        Args:
            app: FastAPI application
            allowed_hosts: List of allowed hostnames
        """
        super().__init__(app)
        self.allowed_hosts = allowed_hosts or ["localhost", "127.0.0.1"]

    async def dispatch(self, request: Request, call_next):
        """Process the request with additional security checks."""
        # Check Host header
        await self._validate_host_header(request)

        # Check for suspicious request patterns
        await self._check_suspicious_patterns(request)

        response = await call_next(request)

        # Add additional security headers
        self._add_security_headers(response)

        return response

    async def _validate_host_header(self, request: Request) -> None:
        """Validate the Host header to prevent host header attacks."""
        host = request.headers.get("host", "").lower()

        # Remove port if present
        if ":" in host:
            host = host.split(":")[0]

        # Allow testserver for testing
        if host == "testserver":
            return

        # Check against allowed hosts
        if host and host not in self.allowed_hosts:
            # Allow subdomains of allowed hosts
            allowed = False
            for allowed_host in self.allowed_hosts:
                if host.endswith("." + allowed_host) or host == allowed_host:
                    allowed = True
                    break

            if not allowed:
                logger.warning(f"Blocked request with suspicious host header: {host}")
                from fastapi import HTTPException
                raise HTTPException(status_code=400, detail="Invalid host header")

    async def _check_suspicious_patterns(self, request: Request) -> None:
        """Check for suspicious request patterns."""
        # Check for directory traversal attempts
        path = request.url.path
        if ".." in path or "%2e%2e" in path.lower() or "%2e%2e%2f" in path.lower():
            logger.warning(f"Potential directory traversal attempt: {path}")
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Invalid request path")

        # Check for suspicious user agents (basic check)
        user_agent = request.headers.get("user-agent", "")
        suspicious_ua_patterns = [
            "sqlmap",
            "nmap",
            "masscan",
            "dirbuster",
            "gobuster",
            "nikto",
            "acunetix",
            "openvas",
        ]

        for pattern in suspicious_ua_patterns:
            if pattern.lower() in user_agent.lower():
                logger.warning(f"Suspicious user agent detected: {user_agent}")
                from fastapi import HTTPException
                raise HTTPException(status_code=403, detail="Access denied")

    def _add_security_headers(self, response: Response) -> None:
        """Add additional security headers to the response."""
        headers = response.headers

        # Remove server header to avoid information disclosure
        if "server" in headers:
            del headers["server"]

        # Add X-Content-Type-Options if not already present
        if "x-content-type-options" not in [h.lower() for h in headers.keys()]:
            headers["X-Content-Type-Options"] = "nosniff"

        # Add X-Frame-Options if not already present
        if "x-frame-options" not in [h.lower() for h in headers.keys()]:
            headers["X-Frame-Options"] = "DENY"


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for secure request logging."""

    def __init__(self, app, log_sensitive_headers: bool = False):
        """Initialize request logging middleware.

        Args:
            app: FastAPI application
            log_sensitive_headers: Whether to log sensitive headers (not recommended for production)
        """
        super().__init__(app)
        self.log_sensitive_headers = log_sensitive_headers

    async def dispatch(self, request: Request, call_next):
        """Log requests with security-relevant information."""
        # Log the request
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "unknown")

        # Create a safe log entry (avoid logging sensitive data)
        log_data = {
            "method": request.method,
            "path": request.url.path,
            "client_ip": client_ip,
            "user_agent_length": len(user_agent),  # Don't log full UA for privacy
        }

        # Add query parameters if not sensitive
        if request.url.query:
            # Check for sensitive parameters
            query_params = dict(request.query_params)
            sensitive_keys = ["password", "token", "key", "secret", "api_key"]

            for key in sensitive_keys:
                if key in query_params:
                    query_params[key] = "[REDACTED]"

            log_data["query_params"] = query_params

        logger.info("Request received", extra=log_data)

        response = await call_next(request)

        # Log the response
        response_log = {
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "client_ip": client_ip,
        }

        if response.status_code >= 400:
            logger.warning("Request failed", extra=response_log)
        else:
            logger.info("Request completed", extra=response_log)

        return response

    def _get_client_ip(self, request: Request) -> str:
        """Get the real client IP address."""
        # Check for forwarded headers
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # Take the first IP in case of multiple
            return str(forwarded).split(",")[0].strip()

        # Check other proxy headers
        for header in ["x-real-ip", "x-client-ip", "cf-connecting-ip"]:
            ip = request.headers.get(header)
            if ip:
                return str(ip).strip()

        # Fall back to direct connection
        if request.client and request.client.host:
            return str(request.client.host)

        return "unknown"


class ContentSecurityMiddleware(BaseHTTPMiddleware):
    """Middleware for content security monitoring."""

    def __init__(self, app, max_request_size: int = 10 * 1024 * 1024):  # 10MB
        """Initialize content security middleware.

        Args:
            app: FastAPI application
            max_request_size: Maximum allowed request size in bytes
        """
        super().__init__(app)
        self.max_request_size = max_request_size

    async def dispatch(self, request: Request, call_next):
        """Monitor request content for security issues."""
        # Check content length
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                if size > self.max_request_size:
                    logger.warning(f"Request too large: {size} bytes")
                    from fastapi import HTTPException
                    raise HTTPException(status_code=413, detail="Request too large")
            except ValueError:
                pass  # Invalid content-length, let FastAPI handle it

        # For POST/PUT/PATCH requests, we could add content inspection here
        # But for now, we'll rely on the validation middleware

        response = await call_next(request)
        return response
