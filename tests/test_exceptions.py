"""Unit tests for custom exception classes."""

from fastapi import HTTPException

from talk2me_ui.exceptions import (
    AudioProcessingError,
    AuthenticationError,
    AuthorizationError,
    ConfigurationError,
    ConflictError,
    ExternalServiceError,
    FileProcessingError,
    NotFoundError,
    RateLimitError,
    Talk2MeException,
    ValidationError,
    create_http_exception,
    handle_exception,
)


class TestTalk2MeException:
    """Test Talk2MeException base class."""

    def test_init_default(self):
        """Test Talk2MeException initialization with defaults."""
        exc = Talk2MeException("Test error")
        assert exc.message == "Test error"
        assert exc.status_code == 500
        assert exc.error_code == "Talk2MeException"
        assert exc.details == {}

    def test_init_custom(self):
        """Test Talk2MeException initialization with custom values."""
        exc = Talk2MeException(
            "Custom error", status_code=400, error_code="CUSTOM_ERROR", details={"key": "value"}
        )
        assert exc.message == "Custom error"
        assert exc.status_code == 400
        assert exc.error_code == "CUSTOM_ERROR"
        assert exc.details == {"key": "value"}

    def test_str(self):
        """Test string representation."""
        exc = Talk2MeException("Test error")
        assert str(exc) == "Test error"


class TestValidationError:
    """Test ValidationError class."""

    def test_init_basic(self):
        """Test ValidationError initialization."""
        exc = ValidationError("Invalid input")
        assert exc.message == "Invalid input"
        assert exc.status_code == 400
        assert exc.error_code == "ValidationError"
        assert exc.details == {}

    def test_init_with_field(self):
        """Test ValidationError with field."""
        exc = ValidationError("Invalid input", field="username")
        assert exc.details["field"] == "username"


class TestAuthenticationError:
    """Test AuthenticationError class."""

    def test_init_default(self):
        """Test AuthenticationError with default message."""
        exc = AuthenticationError()
        assert exc.message == "Authentication required"
        assert exc.status_code == 401

    def test_init_custom(self):
        """Test AuthenticationError with custom message."""
        exc = AuthenticationError("Custom auth error")
        assert exc.message == "Custom auth error"
        assert exc.status_code == 401


class TestAuthorizationError:
    """Test AuthorizationError class."""

    def test_init_default(self):
        """Test AuthorizationError with default message."""
        exc = AuthorizationError()
        assert exc.message == "Insufficient permissions"
        assert exc.status_code == 403

    def test_init_custom(self):
        """Test AuthorizationError with custom message."""
        exc = AuthorizationError("Custom authz error")
        assert exc.message == "Custom authz error"
        assert exc.status_code == 403


class TestNotFoundError:
    """Test NotFoundError class."""

    def test_init_basic(self):
        """Test NotFoundError with resource only."""
        exc = NotFoundError("User")
        assert exc.message == "User not found"
        assert exc.status_code == 404
        assert exc.details["resource"] == "User"

    def test_init_with_id(self):
        """Test NotFoundError with resource and ID."""
        exc = NotFoundError("User", "123")
        assert exc.message == "User not found: 123"
        assert exc.status_code == 404
        assert exc.details["resource"] == "User"
        assert exc.details["resource_id"] == "123"


class TestConflictError:
    """Test ConflictError class."""

    def test_init(self):
        """Test ConflictError initialization."""
        exc = ConflictError("Resource already exists")
        assert exc.message == "Resource already exists"
        assert exc.status_code == 409


class TestRateLimitError:
    """Test RateLimitError class."""

    def test_init_default(self):
        """Test RateLimitError with defaults."""
        exc = RateLimitError()
        assert exc.message == "Rate limit exceeded"
        assert exc.status_code == 429

    def test_init_with_retry_after(self):
        """Test RateLimitError with retry_after."""
        exc = RateLimitError(retry_after=60)
        assert exc.details["retry_after"] == 60


class TestExternalServiceError:
    """Test ExternalServiceError class."""

    def test_init(self):
        """Test ExternalServiceError initialization."""
        exc = ExternalServiceError("API", "Connection failed")
        assert exc.message == "API error: Connection failed"
        assert exc.status_code == 502
        assert exc.details["service"] == "API"


class TestConfigurationError:
    """Test ConfigurationError class."""

    def test_init(self):
        """Test ConfigurationError initialization."""
        exc = ConfigurationError("Invalid configuration")
        assert exc.message == "Invalid configuration"
        assert exc.status_code == 500


class TestFileProcessingError:
    """Test FileProcessingError class."""

    def test_init_basic(self):
        """Test FileProcessingError without filename."""
        exc = FileProcessingError("File processing failed")
        assert exc.message == "File processing failed"
        assert exc.status_code == 400

    def test_init_with_filename(self):
        """Test FileProcessingError with filename."""
        exc = FileProcessingError("File processing failed", filename="test.txt")
        assert exc.details["filename"] == "test.txt"


class TestAudioProcessingError:
    """Test AudioProcessingError class."""

    def test_init(self):
        """Test AudioProcessingError initialization."""
        exc = AudioProcessingError("Audio processing failed")
        assert exc.message == "Audio processing failed"
        assert exc.status_code == 400


class TestCreateHttpException:
    """Test create_http_exception function."""

    def test_create_http_exception(self):
        """Test converting Talk2MeException to HTTPException."""
        exc = ValidationError("Test error", field="test")
        http_exc = create_http_exception(exc)

        assert isinstance(http_exc, HTTPException)
        assert http_exc.status_code == 400
        assert http_exc.detail["error"] == "ValidationError"
        assert http_exc.detail["message"] == "Test error"
        assert http_exc.detail["details"]["field"] == "test"


class TestHandleException:
    """Test handle_exception function."""

    def test_handle_talk2me_exception(self):
        """Test handling Talk2MeException."""
        exc = ValidationError("Test error")
        http_exc = handle_exception(exc)

        assert isinstance(http_exc, HTTPException)
        assert http_exc.status_code == 400

    def test_handle_value_error(self):
        """Test handling ValueError."""
        exc = ValueError("Invalid value")
        http_exc = handle_exception(exc)

        assert isinstance(http_exc, HTTPException)
        assert http_exc.status_code == 400
        assert http_exc.detail == "Invalid value"

    def test_handle_file_not_found_error(self):
        """Test handling FileNotFoundError."""
        exc = FileNotFoundError("File not found")
        http_exc = handle_exception(exc)

        assert isinstance(http_exc, HTTPException)
        assert http_exc.status_code == 404
        assert http_exc.detail == "File not found"

    def test_handle_permission_error(self):
        """Test handling PermissionError."""
        exc = PermissionError("Permission denied")
        http_exc = handle_exception(exc)

        assert isinstance(http_exc, HTTPException)
        assert http_exc.status_code == 403
        assert http_exc.detail == "Permission denied"

    def test_handle_generic_exception(self):
        """Test handling generic exception."""
        exc = RuntimeError("Something went wrong")
        http_exc = handle_exception(exc)

        assert isinstance(http_exc, HTTPException)
        assert http_exc.status_code == 500
        assert http_exc.detail == "Internal server error"
