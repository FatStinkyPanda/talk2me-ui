"""CSRF protection middleware and utilities for Talk2Me UI.

This module provides Cross-Site Request Forgery (CSRF) protection
for web forms and API endpoints.
"""

import hashlib
import hmac
import secrets
import time

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware


class CSRFProtection:
    """CSRF protection utilities."""

    def __init__(self, secret_key: str, token_lifetime: int = 3600):
        """Initialize CSRF protection.

        Args:
            secret_key: Secret key for token signing
            token_lifetime: Token lifetime in seconds (default: 1 hour)
        """
        self.secret_key = secret_key.encode()
        self.token_lifetime = token_lifetime

    def generate_token(self, session_id: str) -> str:
        """Generate a CSRF token for a session.

        Args:
            session_id: Unique session identifier

        Returns:
            CSRF token string
        """
        # Create token data: timestamp + random nonce
        timestamp = str(int(time.time()))
        nonce = secrets.token_hex(16)

        # Create message to sign
        message = f"{session_id}:{timestamp}:{nonce}"

        # Create HMAC signature
        signature = hmac.new(self.secret_key, message.encode(), hashlib.sha256).hexdigest()

        # Return token: timestamp.nonce.signature
        return f"{timestamp}.{nonce}.{signature}"

    def validate_token(self, token: str, session_id: str) -> bool:
        """Validate a CSRF token.

        Args:
            token: CSRF token to validate
            session_id: Session identifier

        Returns:
            True if token is valid, False otherwise
        """
        try:
            # Parse token
            parts = token.split(".")
            if len(parts) != 3:
                return False

            timestamp_str, nonce, signature = parts

            # Check timestamp (prevent replay attacks)
            timestamp = int(timestamp_str)
            current_time = int(time.time())

            if current_time - timestamp > self.token_lifetime:
                return False

            # Recreate message and verify signature
            message = f"{session_id}:{timestamp_str}:{nonce}"
            expected_signature = hmac.new(
                self.secret_key, message.encode(), hashlib.sha256
            ).hexdigest()

            return hmac.compare_digest(signature, expected_signature)

        except (ValueError, IndexError):
            return False

    def get_session_id(self, request: Request) -> str:
        """Get or create a session ID for the request.

        Args:
            request: FastAPI request object

        Returns:
            Session ID string
        """
        # For now, use client IP + user agent as session identifier
        # In production, use proper session management
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("User-Agent", "unknown")

        # Create a stable session ID
        session_data = f"{client_ip}:{user_agent}"
        return hashlib.sha256(session_data.encode()).hexdigest()[:32]


class CSRFMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for CSRF protection."""

    def __init__(self, app, secret_key: str, exempt_paths: list[str] | None = None):
        """Initialize CSRF middleware.

        Args:
            app: FastAPI application
            secret_key: Secret key for token signing
            exempt_paths: List of paths to exempt from CSRF checks
        """
        super().__init__(app)
        self.csrf = CSRFProtection(secret_key)
        self.exempt_paths = exempt_paths or ["/api/health", "/metrics"]

    async def dispatch(self, request: Request, call_next):
        """Process the request and check CSRF token if needed."""
        # Skip CSRF check for safe methods
        if request.method in ["GET", "HEAD", "OPTIONS"]:
            return await call_next(request)

        # Skip CSRF check for exempt paths
        if any(request.url.path.startswith(path) for path in self.exempt_paths):
            return await call_next(request)

        # Check for CSRF token in headers or form data
        token = self._get_csrf_token(request)

        if not token:
            raise HTTPException(status_code=403, detail="CSRF token missing")

        # Validate token
        session_id = self.csrf.get_session_id(request)
        if not self.csrf.validate_token(token, session_id):
            raise HTTPException(status_code=403, detail="CSRF token invalid or expired")

        # Add CSRF token to request state for use in handlers
        request.state.csrf_token = token
        request.state.session_id = session_id

        response = await call_next(request)
        return response

    def _get_csrf_token(self, request: Request) -> str | None:
        """Extract CSRF token from request.

        Args:
            request: FastAPI request object

        Returns:
            CSRF token if found, None otherwise
        """
        # Check headers first (for API requests)
        token = request.headers.get("X-CSRF-Token")
        if token:
            return str(token)

        # Check form data (for form submissions)
        if hasattr(request, "_form") and request._form:
            form_token = request._form.get("csrf_token")
            return str(form_token) if form_token else None

        # Check query parameters (fallback)
        query_token = request.query_params.get("csrf_token")
        return str(query_token) if query_token else None


# Global CSRF protection instance
def get_csrf_protection() -> CSRFProtection:
    """Get the global CSRF protection instance."""
    import os

    secret_key = os.getenv("CSRF_SECRET", "default-csrf-secret-change-in-production")
    return CSRFProtection(secret_key)


# Template context processor for CSRF tokens
def get_csrf_context(request: Request) -> dict:
    """Get CSRF context for templates.

    Args:
        request: FastAPI request object

    Returns:
        Dictionary with CSRF token
    """
    csrf = get_csrf_protection()
    session_id = csrf.get_session_id(request)
    token = csrf.generate_token(session_id)

    return {"csrf_token": token}
