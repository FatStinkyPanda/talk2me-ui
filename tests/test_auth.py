"""Tests for authentication system."""

import pytest

from talk2me_ui.auth import (
    SessionManager,
    User,
    UserManager,
    generate_session_cookie,
    parse_session_cookie,
)


class TestUserModel:
    """Test User model."""

    def test_user_creation(self):
        """Test user creation with valid data."""
        user = User(username="testuser", email="test@example.com", password_hash="$2b$12$test.hash")

        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.password_hash == "$2b$12$test.hash"
        assert user.is_active is True
        assert user.id is not None

    def test_username_validation(self):
        """Test username validation."""
        # Valid bcrypt hash
        valid_hash = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LezK0C.i/UeO8i0Pu"

        # Valid username
        user = User(username="test_user123", email="test@example.com", password_hash=valid_hash)
        assert user.username == "test_user123"

        # Invalid username with special chars
        with pytest.raises(ValueError, match="Username must contain only"):
            User(username="test@user", email="test@example.com", password_hash=valid_hash)

    def test_password_hash_validation(self):
        """Test password hash validation."""
        # Valid hash
        user = User(username="test", email="test@example.com", password_hash="$2b$12$validhash")
        assert user.password_hash == "$2b$12$validhash"

        # Invalid hash
        with pytest.raises(ValueError, match="Invalid password hash format"):
            User(username="test", email="test@example.com", password_hash="invalid")


class TestUserManager:
    """Test UserManager functionality."""

    def test_create_user(self, tmp_path):
        """Test user creation."""
        manager = UserManager(tmp_path / "users")

        user = manager.create_user("testuser", "test@example.com", "password123")

        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.is_active is True

        # Test duplicate username
        with pytest.raises(ValueError, match="Username already exists"):
            manager.create_user("testuser", "other@example.com", "password")

        # Test duplicate email
        with pytest.raises(ValueError, match="Email already exists"):
            manager.create_user("otheruser", "test@example.com", "password")

    def test_authenticate_user(self, tmp_path):
        """Test user authentication."""
        manager = UserManager(tmp_path / "users")

        # Create user
        manager.create_user("testuser", "test@example.com", "password123")

        # Successful authentication
        user = manager.authenticate_user("testuser", "password123")
        assert user is not None
        assert user.username == "testuser"

        # Failed authentication - wrong password
        user = manager.authenticate_user("testuser", "wrongpassword")
        assert user is None

        # Failed authentication - non-existent user
        user = manager.authenticate_user("nonexistent", "password")
        assert user is None


class TestSessionManager:
    """Test SessionManager functionality."""

    def test_create_session(self, tmp_path):
        """Test session creation."""
        manager = SessionManager(tmp_path / "sessions")

        session = manager.create_session("user123", "127.0.0.1", "Mozilla/5.0")

        assert session.user_id == "user123"
        assert session.ip_address == "127.0.0.1"
        assert session.user_agent == "Mozilla/5.0"
        assert not session.is_expired

    def test_session_expiry(self, tmp_path):
        """Test session expiry."""
        manager = SessionManager(tmp_path / "sessions", session_timeout=0)  # Immediate expiry

        session = manager.create_session("user123")
        assert session.is_expired  # Should be expired immediately

    def test_get_session(self, tmp_path):
        """Test session retrieval."""
        manager = SessionManager(tmp_path / "sessions")

        session = manager.create_session("user123")
        retrieved = manager.get_session(session.id)

        assert retrieved is not None
        assert retrieved.id == session.id
        assert retrieved.user_id == "user123"


class TestSessionCookie:
    """Test session cookie functions."""

    def test_generate_parse_cookie(self):
        """Test cookie generation and parsing."""
        session_id = "test-session-123"
        cookie = generate_session_cookie(type("MockSession", (), {"id": session_id})())

        assert "." in cookie
        parsed_id = parse_session_cookie(cookie)
        assert parsed_id == session_id

    def test_parse_invalid_cookie(self):
        """Test parsing invalid cookies."""
        assert parse_session_cookie("invalid") is None
        assert parse_session_cookie("") is None


class TestIntegration:
    """Integration tests for auth system."""

    def test_full_auth_flow(self, tmp_path):
        """Test complete authentication flow."""
        # Setup managers
        user_mgr = UserManager(tmp_path / "users")
        session_mgr = SessionManager(tmp_path / "sessions")

        # Register user
        user = user_mgr.create_user("testuser", "test@example.com", "password123")
        assert user is not None

        # Authenticate user
        auth_user = user_mgr.authenticate_user("testuser", "password123")
        assert auth_user is not None
        assert auth_user.id == user.id

        # Create session
        session = session_mgr.create_session(user.id, "127.0.0.1")
        assert session is not None

        # Generate cookie
        cookie = generate_session_cookie(session)
        assert cookie is not None

        # Parse cookie and get user
        parsed_session_id = parse_session_cookie(cookie)
        assert parsed_session_id == session.id

        retrieved_session = session_mgr.get_session(parsed_session_id)
        assert retrieved_session is not None
        assert retrieved_session.user_id == user.id

        # Get current user
        current_user = user_mgr.get_user_by_id(retrieved_session.user_id)
        assert current_user is not None
        assert current_user.username == "testuser"
