"""Security headers middleware for Talk2Me UI.

This module provides comprehensive security headers middleware
to protect against common web vulnerabilities.
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses."""

    def __init__(
        self,
        app,
        content_security_policy: dict[str, list[str]] | None = None,
        hsts_max_age: int = 31536000,  # 1 year
        hsts_include_subdomains: bool = True,
        hsts_preload: bool = False,
        frame_options: str = "DENY",
        content_type_options: str = "nosniff",
        xss_protection: str = "1; mode=block",
        referrer_policy: str = "strict-origin-when-cross-origin",
        permissions_policy: dict[str, list[str]] | None = None,
        cross_origin_embedder_policy: str | None = None,
        cross_origin_opener_policy: str | None = None,
        cross_origin_resource_policy: str | None = None,
    ):
        """Initialize security headers middleware.

        Args:
            app: FastAPI application
            content_security_policy: CSP directives
            hsts_max_age: HSTS max-age in seconds
            hsts_include_subdomains: Include subdomains in HSTS
            hsts_preload: Enable HSTS preload
            frame_options: X-Frame-Options value
            content_type_options: X-Content-Type-Options value
            xss_protection: X-XSS-Protection value
            referrer_policy: Referrer-Policy value
            permissions_policy: Permissions-Policy directives
            cross_origin_embedder_policy: COEP value
            cross_origin_opener_policy: COOP value
            cross_origin_resource_policy: CORP value
        """
        super().__init__(app)

        # Build Content Security Policy
        self.csp = self._build_csp(content_security_policy or self._get_default_csp())

        # Build HSTS header
        hsts_parts = [f"max-age={hsts_max_age}"]
        if hsts_include_subdomains:
            hsts_parts.append("includeSubDomains")
        if hsts_preload:
            hsts_parts.append("preload")
        self.hsts = "; ".join(hsts_parts)

        # Store other headers
        self.frame_options = frame_options
        self.content_type_options = content_type_options
        self.xss_protection = xss_protection
        self.referrer_policy = referrer_policy

        # Build Permissions Policy
        self.permissions_policy = self._build_permissions_policy(
            permissions_policy or self._get_default_permissions_policy()
        )

        # Cross-origin policies
        self.cross_origin_embedder_policy = cross_origin_embedder_policy
        self.cross_origin_opener_policy = cross_origin_opener_policy
        self.cross_origin_resource_policy = cross_origin_resource_policy

    def _get_default_csp(self) -> dict[str, list[str]]:
        """Get default Content Security Policy directives."""
        return {
            "default-src": ["'self'"],
            "script-src": ["'self'", "'unsafe-inline'"],  # Allow inline scripts for now
            "style-src": ["'self'", "'unsafe-inline'"],  # Allow inline styles
            "img-src": ["'self'", "data:", "blob:"],  # Allow data URLs and blobs
            "font-src": ["'self'"],
            "connect-src": ["'self'", "ws:", "wss:"],  # Allow WebSocket connections
            "media-src": ["'self'", "blob:"],  # Allow audio/video blobs
            "object-src": ["'none'"],  # Block plugins
            "frame-src": ["'none'"],  # Block frames
            "base-uri": ["'self'"],
            "form-action": ["'self'"],
        }

    def _get_default_permissions_policy(self) -> dict[str, list[str]]:
        """Get default Permissions Policy directives."""
        return {
            "camera": ["()"],  # Deny camera access
            "microphone": ["()"],  # Deny microphone access (we handle this separately)
            "geolocation": ["()"],  # Deny geolocation
            "payment": ["()"],  # Deny payment APIs
            "usb": ["()"],  # Deny USB access
            "magnetometer": ["()"],  # Deny magnetometer
            "accelerometer": ["()"],  # Deny accelerometer
            "gyroscope": ["()"],  # Deny gyroscope
            "ambient-light-sensor": ["()"],  # Deny ambient light sensor
        }

    def _build_csp(self, directives: dict[str, list[str]]) -> str:
        """Build CSP header value from directives."""
        csp_parts = []
        for directive, values in directives.items():
            if values:
                csp_parts.append(f"{directive} {' '.join(values)}")
        return "; ".join(csp_parts)

    def _build_permissions_policy(self, directives: dict[str, list[str]]) -> str:
        """Build Permissions-Policy header value from directives."""
        policy_parts = []
        for directive, values in directives.items():
            if values:
                policy_parts.append(f"{directive}={' '.join(values)}")
        return ", ".join(policy_parts)

    async def dispatch(self, request: Request, call_next):
        """Add security headers to the response."""
        response = await call_next(request)

        # Only add headers to HTML responses and API responses
        if self._should_add_headers(request, response):
            self._add_security_headers(response)

        return response

    def _should_add_headers(self, request: Request, response: Response) -> bool:
        """Determine if security headers should be added to this response."""
        # Add to HTML pages
        if "text/html" in response.headers.get("content-type", ""):
            return True

        # Add to API responses
        if request.url.path.startswith("/api/"):
            return True

        # Add to static files that could be embedded
        if request.url.path.startswith("/static/"):
            return True

        return False

    def _add_security_headers(self, response: Response) -> None:
        """Add all security headers to the response."""
        headers = response.headers

        # Content Security Policy
        if self.csp:
            headers["Content-Security-Policy"] = self.csp

        # HTTP Strict Transport Security (only for HTTPS)
        if self.hsts:
            headers["Strict-Transport-Security"] = self.hsts

        # Frame Options
        if self.frame_options:
            headers["X-Frame-Options"] = self.frame_options

        # Content Type Options
        if self.content_type_options:
            headers["X-Content-Type-Options"] = self.content_type_options

        # XSS Protection
        if self.xss_protection:
            headers["X-XSS-Protection"] = self.xss_protection

        # Referrer Policy
        if self.referrer_policy:
            headers["Referrer-Policy"] = self.referrer_policy

        # Permissions Policy
        if self.permissions_policy:
            headers["Permissions-Policy"] = self.permissions_policy

        # Cross-Origin policies
        if self.cross_origin_embedder_policy:
            headers["Cross-Origin-Embedder-Policy"] = self.cross_origin_embedder_policy

        if self.cross_origin_opener_policy:
            headers["Cross-Origin-Opener-Policy"] = self.cross_origin_opener_policy

        if self.cross_origin_resource_policy:
            headers["Cross-Origin-Resource-Policy"] = self.cross_origin_resource_policy

        # Additional security headers
        headers["X-Permitted-Cross-Domain-Policies"] = "none"


class SecurityHeadersConfig:
    """Configuration class for security headers."""

    @staticmethod
    def get_production_config() -> dict:
        """Get production-ready security headers configuration."""
        return {
            "content_security_policy": {
                "default-src": ["'self'"],
                "script-src": ["'self'"],  # Remove 'unsafe-inline' in production
                "style-src": ["'self'"],  # Remove 'unsafe-inline' in production
                "img-src": ["'self'", "data:", "blob:"],
                "font-src": ["'self'"],
                "connect-src": ["'self'", "ws:", "wss:"],
                "media-src": ["'self'", "blob:"],
                "object-src": ["'none'"],
                "frame-src": ["'none'"],
                "base-uri": ["'self'"],
                "form-action": ["'self'"],
                "upgrade-insecure-requests": [],  # Enable HTTPS upgrades
            },
            "hsts_max_age": 31536000,  # 1 year
            "hsts_include_subdomains": True,
            "hsts_preload": False,  # Set to True only after thorough testing
            "frame_options": "DENY",
            "content_type_options": "nosniff",
            "xss_protection": "1; mode=block",
            "referrer_policy": "strict-origin-when-cross-origin",
            "cross_origin_embedder_policy": "require-corp",
            "cross_origin_opener_policy": "same-origin",
            "cross_origin_resource_policy": "same-origin",
        }

    @staticmethod
    def get_development_config() -> dict:
        """Get development-friendly security headers configuration."""
        config = SecurityHeadersConfig.get_production_config()
        # Relax CSP for development
        config["content_security_policy"]["script-src"].append("'unsafe-inline'")
        config["content_security_policy"]["style-src"].append("'unsafe-inline'")
        # Disable HSTS preload in development
        config["hsts_preload"] = False
        return config
