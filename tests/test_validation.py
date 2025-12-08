"""Unit tests for validation module."""

import os
from io import BytesIO
from unittest.mock import Mock, patch

import pytest
from fastapi import Request, UploadFile

from talk2me_ui.validation import (
    EnvironmentValidator,
    InputSanitizer,
    ValidationMiddleware,
    validate_environment_on_startup,
    validate_file_upload,
    validate_text_input,
)


class TestValidationMiddleware:
    """Test ValidationMiddleware class."""

    @pytest.fixture
    def middleware(self):
        """Create validation middleware instance."""
        return ValidationMiddleware()

    @pytest.fixture
    def mock_request(self):
        """Create mock request."""
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "127.0.0.1"
        request.headers = {}
        return request

    def test_init(self, middleware):
        """Test middleware initialization."""
        assert middleware.max_requests_per_minute == 60
        assert isinstance(middleware.request_counts, dict)

    @pytest.mark.asyncio
    async def test_validate_request_success(self, middleware, mock_request):
        """Test successful request validation."""
        await middleware.validate_request(mock_request)
        # Should not raise

    def test_get_client_ip_direct(self, middleware, mock_request):
        """Test getting client IP from direct connection."""
        ip = middleware._get_client_ip(mock_request)
        assert ip == "127.0.0.1"

    def test_get_client_ip_forwarded(self, middleware, mock_request):
        """Test getting client IP from forwarded header."""
        mock_request.headers = {"X-Forwarded-For": "192.168.1.1, 10.0.0.1"}
        ip = middleware._get_client_ip(mock_request)
        assert ip == "192.168.1.1"

    def test_get_client_ip_no_client(self, middleware, mock_request):
        """Test getting client IP when no client info."""
        mock_request.client = None
        ip = middleware._get_client_ip(mock_request)
        assert ip == "unknown"

    @pytest.mark.asyncio
    async def test_check_rate_limit_under_limit(self, middleware):
        """Test rate limit check when under limit."""
        client_ip = "127.0.0.1"
        await middleware._check_rate_limit(client_ip)
        # Should not raise

    @pytest.mark.asyncio
    async def test_check_rate_limit_over_limit(self, middleware):
        """Test rate limit check when over limit."""
        from talk2me_ui.exceptions import RateLimitError

        client_ip = "127.0.0.1"
        # Fill up the rate limit
        for _ in range(60):
            await middleware._check_rate_limit(client_ip)

        with pytest.raises(RateLimitError):
            await middleware._check_rate_limit(client_ip)

    @pytest.mark.asyncio
    async def test_validate_request_size_valid(self, middleware, mock_request):
        """Test request size validation with valid size."""
        mock_request.headers = {"content-length": "1024"}
        await middleware._validate_request_size(mock_request)
        # Should not raise

    @pytest.mark.asyncio
    async def test_validate_request_size_too_large(self, middleware, mock_request):
        """Test request size validation with too large size."""
        from talk2me_ui.exceptions import ValidationError

        mock_request.headers = {"content-length": "20000000"}  # 20MB
        with pytest.raises(ValidationError):
            await middleware._validate_request_size(mock_request)

    def test_validate_headers_valid(self, middleware, mock_request):
        """Test header validation with valid headers."""
        mock_request.headers = {"user-agent": "test", "accept": "application/json"}
        middleware._validate_headers(mock_request)
        # Should not raise

    def test_validate_headers_suspicious(self, middleware, mock_request):
        """Test header validation with suspicious content."""
        from talk2me_ui.exceptions import ValidationError

        mock_request.headers = {"user-agent": "<script>alert('xss')</script>"}
        with pytest.raises(ValidationError):
            middleware._validate_headers(mock_request)


class TestTextInputValidation:
    """Test text input validation decorator."""

    @pytest.mark.asyncio
    async def test_validate_text_input_valid(self):
        """Test text input validation with valid input."""

        @validate_text_input(min_length=5, max_length=20)
        async def dummy_func(text: str):
            return text

        result = await dummy_func(text="valid text")
        assert result == "valid text"

    @pytest.mark.asyncio
    async def test_validate_text_input_too_short(self):
        """Test text input validation with too short input."""
        from talk2me_ui.exceptions import ValidationError

        @validate_text_input(min_length=5)
        async def dummy_func(text: str):
            return text

        with pytest.raises(ValidationError, match="too short"):
            await dummy_func(text="hi")

    @pytest.mark.asyncio
    async def test_validate_text_input_too_long(self):
        """Test text input validation with too long input."""
        from talk2me_ui.exceptions import ValidationError

        @validate_text_input(max_length=10)
        async def dummy_func(text: str):
            return text

        with pytest.raises(ValidationError, match="too long"):
            await dummy_func(text="this is way too long")

    @pytest.mark.asyncio
    async def test_validate_text_input_invalid_chars(self):
        """Test text input validation with invalid characters."""
        from talk2me_ui.exceptions import ValidationError

        @validate_text_input(allowed_chars="abc")
        async def dummy_func(text: str):
            return text

        with pytest.raises(ValidationError, match="invalid characters"):
            await dummy_func(text="abc123")

    @pytest.mark.asyncio
    async def test_validate_text_input_html_disallowed(self):
        """Test text input validation with HTML when disallowed."""
        from talk2me_ui.exceptions import ValidationError

        @validate_text_input(disallow_html=True)
        async def dummy_func(text: str):
            return text

        with pytest.raises(ValidationError, match="HTML tags"):
            await dummy_func(text="<script>alert('xss')</script>")


class TestFileUploadValidation:
    """Test file upload validation decorator."""

    @pytest.mark.asyncio
    async def test_validate_file_upload_valid(self):
        """Test file upload validation with valid file."""

        @validate_file_upload(allowed_extensions=[".txt"], max_size=1024)
        async def dummy_func(_file: UploadFile):
            return "ok"

        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "test.txt"
        mock_file.content_type = "text/plain"
        mock_file.file = BytesIO(b"test content")

        result = await dummy_func(file=mock_file)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_validate_file_upload_invalid_extension(self):
        """Test file upload validation with invalid extension."""
        from talk2me_ui.exceptions import ValidationError

        @validate_file_upload(allowed_extensions=[".txt"])
        async def dummy_func(_file: UploadFile):
            return "ok"

        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "test.exe"

        with pytest.raises(ValidationError, match="File type not allowed"):
            await dummy_func(file=mock_file)

    @pytest.mark.asyncio
    async def test_validate_file_upload_invalid_mime(self):
        """Test file upload validation with invalid MIME type."""
        from talk2me_ui.exceptions import ValidationError

        @validate_file_upload(allowed_mime_types=["text/plain"])
        async def dummy_func(_file: UploadFile):
            return "ok"

        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "test.txt"
        mock_file.content_type = "application/octet-stream"

        with pytest.raises(ValidationError, match="File type not allowed"):
            await dummy_func(file=mock_file)

    @pytest.mark.asyncio
    async def test_validate_file_upload_too_large(self):
        """Test file upload validation with file too large."""
        from talk2me_ui.exceptions import ValidationError

        @validate_file_upload(max_size=10)
        async def dummy_func(_file: UploadFile):
            return "ok"

        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "test.txt"
        mock_file.file = BytesIO(b"x" * 20)  # 20 bytes

        with pytest.raises(ValidationError, match="File too large"):
            await dummy_func(file=mock_file)


class TestInputSanitizer:
    """Test InputSanitizer class."""

    def test_sanitize_text_empty(self):
        """Test sanitizing empty text."""
        result = InputSanitizer.sanitize_text("")
        assert result == ""

    def test_sanitize_text_normal(self):
        """Test sanitizing normal text."""
        result = InputSanitizer.sanitize_text("Hello world")
        assert result == "Hello world"

    def test_sanitize_text_null_bytes(self):
        """Test sanitizing text with null bytes."""
        result = InputSanitizer.sanitize_text("Hello\x00world")
        assert result == "Helloworld"

    def test_sanitize_text_control_chars(self):
        """Test sanitizing text with control characters."""
        result = InputSanitizer.sanitize_text("Hello\x01\x02world\x7f")
        assert result == "Helloworld"

    def test_sanitize_filename_empty(self):
        """Test sanitizing empty filename."""
        result = InputSanitizer.sanitize_filename("")
        assert result == ""

    def test_sanitize_filename_normal(self):
        """Test sanitizing normal filename."""
        result = InputSanitizer.sanitize_filename("test.txt")
        assert result == "test.txt"

    def test_sanitize_filename_path_traversal(self):
        """Test sanitizing filename with path traversal."""
        result = InputSanitizer.sanitize_filename("../../etc/passwd")
        assert result == "....etcpasswd"

    def test_sanitize_filename_control_chars(self):
        """Test sanitizing filename with control characters."""
        result = InputSanitizer.sanitize_filename("test\x00\x01.txt")
        assert result == "test.txt"

    def test_sanitize_filename_too_long(self):
        """Test sanitizing filename that's too long."""
        long_name = "a" * 300 + ".txt"
        result = InputSanitizer.sanitize_filename(long_name)
        assert len(result) <= 255
        assert result.endswith(".txt")


class TestEnvironmentValidator:
    """Test EnvironmentValidator class."""

    @patch.dict(os.environ, {"APP_ENV": "development", "LOG_LEVEL": "INFO"}, clear=True)
    def test_validate_environment_valid(self):
        """Test environment validation with valid variables."""
        issues = EnvironmentValidator.validate_environment()
        # Should have no issues for basic setup
        assert isinstance(issues, list)

    @patch.dict(os.environ, {"APP_ENV": "invalid"}, clear=True)
    def test_validate_environment_invalid_app_env(self):
        """Test environment validation with invalid APP_ENV."""
        issues = EnvironmentValidator.validate_environment()
        assert any("APP_ENV" in issue for issue in issues)

    @patch.dict(os.environ, {"APP_ENV": "development", "LOG_LEVEL": "INVALID"}, clear=True)
    def test_validate_environment_invalid_log_level(self):
        """Test environment validation with invalid LOG_LEVEL."""
        issues = EnvironmentValidator.validate_environment()
        assert any("LOG_LEVEL" in issue for issue in issues)

    @patch.dict(os.environ, {"APP_ENV": "development", "DEBUG": "invalid"}, clear=True)
    def test_validate_environment_invalid_debug(self):
        """Test environment validation with invalid DEBUG."""
        issues = EnvironmentValidator.validate_environment()
        assert any("DEBUG" in issue for issue in issues)

    @patch.dict(os.environ, {"APP_ENV": "development", "PORT": "99999"}, clear=True)
    def test_validate_environment_invalid_port(self):
        """Test environment validation with invalid PORT."""
        issues = EnvironmentValidator.validate_environment()
        assert any("PORT" in issue for issue in issues)

    @patch.dict(os.environ, {"APP_ENV": "development", "WORKERS": "0"}, clear=True)
    def test_validate_environment_invalid_workers(self):
        """Test environment validation with invalid WORKERS."""
        issues = EnvironmentValidator.validate_environment()
        assert any("WORKERS" in issue for issue in issues)

    @patch.dict(os.environ, {"APP_ENV": "development", "MAX_FILE_SIZE": "-1"}, clear=True)
    def test_validate_environment_invalid_max_file_size(self):
        """Test environment validation with invalid MAX_FILE_SIZE."""
        issues = EnvironmentValidator.validate_environment()
        assert any("MAX_FILE_SIZE" in issue for issue in issues)

    @patch.dict(os.environ, {"APP_ENV": "development", "ENABLE_METRICS": "invalid"}, clear=True)
    def test_validate_environment_invalid_boolean(self):
        """Test environment validation with invalid boolean."""
        issues = EnvironmentValidator.validate_environment()
        assert any("ENABLE_METRICS" in issue for issue in issues)

    @patch.dict(
        os.environ, {"APP_ENV": "development", "SECRET_KEY": "short"}, clear=True
    )  # pragma: allowlist secret
    def test_validate_environment_weak_secret(self):
        """Test environment validation with weak secret."""
        issues = EnvironmentValidator.validate_environment()
        assert any("SECRET_KEY" in issue for issue in issues)

    @patch.dict(
        os.environ,
        {
            "APP_ENV": "development",
            "SECRET_KEY": "your-secure-random-secret-key-here",
        },  # pragma: allowlist secret
        clear=True,
    )
    def test_validate_environment_default_secret(self):
        """Test environment validation with default secret."""
        issues = EnvironmentValidator.validate_environment()
        assert any("default/placeholder value" in issue for issue in issues)

    def test_get_validation_summary(self):
        """Test getting validation summary."""
        summary = EnvironmentValidator.get_validation_summary()
        assert isinstance(summary, dict)
        assert "environment" in summary
        assert "total_issues" in summary
        assert "issues" in summary
        assert "is_valid" in summary


class TestValidateEnvironmentOnStartup:
    """Test validate_environment_on_startup function."""

    @patch("talk2me_ui.validation.EnvironmentValidator.get_validation_summary")
    def test_validate_environment_on_startup_valid(self, mock_summary):
        """Test startup validation with valid environment."""
        mock_summary.return_value = {"issues": [], "is_valid": True}
        validate_environment_on_startup()
        # Should not raise

    @patch("talk2me_ui.validation.EnvironmentValidator.get_validation_summary")
    def test_validate_environment_on_startup_critical_issues(self, mock_summary):
        """Test startup validation with critical issues."""
        mock_summary.return_value = {
            "environment": "development",
            "total_issues": 1,
            "issues": ["Required variable 'APP_ENV' is not set"],
            "is_valid": False,
        }
        with pytest.raises(ValueError, match="Critical environment configuration issues"):
            validate_environment_on_startup()

    @patch("talk2me_ui.validation.EnvironmentValidator.get_validation_summary")
    def test_validate_environment_on_startup_non_critical_issues(self, mock_summary):
        """Test startup validation with non-critical issues."""
        mock_summary.return_value = {
            "environment": "production",
            "total_issues": 1,
            "issues": ["DEBUG should be 'false' in production environment"],
            "is_valid": False,
        }
        validate_environment_on_startup()
        # Should not raise for non-critical issues
