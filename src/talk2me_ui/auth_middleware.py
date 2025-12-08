"""Authentication middleware for Talk2Me UI.

This module provides middleware for protecting routes with authentication
and managing user sessions via secure cookies.
"""

import logging
from typing import Optional

from fastapi import Request, Response
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .auth import get_current_user, parse_session_cookie

logger = logging.getLogger("talk2me_ui.auth_middleware")


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Middleware for authentication and session management."""

    def __init__(self, app, exclude_paths: Optional[list[str]] = None):
        """Initialize authentication middleware.

        Args:
            app: FastAPI application
            exclude_paths: Paths that don't require authentication
        """
        super().__init__(app)
        self.exclude_paths = exclude_paths or [
            "/auth/login",
            "/auth/register",
            "/api/health",
            "/metrics",
            "/static",
            "/favicon.ico"
        ]

    async def dispatch(self, request: Request, call_next):
        """Process request with authentication check."""
        # Check if path requires authentication
        if self._should_exclude_path(request.url.path):
            return await call_next(request)

        # Get session from cookie
        session_cookie = request.cookies.get("session_id")
        if not session_cookie:
            return self._unauthorized_response(request)

        # Parse and validate session
        session_id = parse_session_cookie(session_cookie)
        if not session_id:
            return self._unauthorized_response(request)

        # Get current user
        user = get_current_user(session_id)
        if not user:
            return self._unauthorized_response(request)

        # Add user to request state
        request.state.user = user
        request.state.session_id = session_id

        # Log authenticated request
        logger.debug(
            "Authenticated request",
            extra={
                "user_id": user.id,
                "username": user.username,
                "path": request.url.path,
                "method": request.method,
            }
        )

        response = await call_next(request)

        # Ensure session cookie is set with secure attributes
        self._set_session_cookie(response, session_cookie)

        return response

    def _should_exclude_path(self, path: str) -> bool:
        """Check if path should be excluded from authentication."""
        for exclude_path in self.exclude_paths:
            if path.startswith(exclude_path):
                return True
        return False

    def _unauthorized_response(self, request: Request) -> Response:
        """Return appropriate unauthorized response."""
        # For API requests, return JSON
        if request.url.path.startswith("/api/"):
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=401,
                content={"error": "Authentication required", "message": "Please log in"}
            )

        # For web requests, redirect to login
        return RedirectResponse(url="/auth/login", status_code=302)

    @staticmethod
    def _set_session_cookie(response: Response, session_cookie: str) -> None:
        """Set secure session cookie on response."""
        response.set_cookie(
            key="session_id",
            value=session_cookie,
            httponly=True,  # Prevent JavaScript access
            secure=True,     # HTTPS only in production
            samesite="lax",  # CSRF protection
            max_age=24 * 60 * 60,  # 24 hours
            path="/"
        )


def get_current_user_dependency(request: Request):
    """FastAPI dependency to get current authenticated user.

    Usage:
        @app.get("/protected")
        async def protected_route(current_user: User = Depends(get_current_user_dependency)):
            return {"user": current_user.username}
    """
    user = getattr(request.state, "user", None)
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Authentication required")
    return user
