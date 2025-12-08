"""Authentication and session management for Talk2Me UI.

This module provides user authentication, session management, and security
features including password hashing with bcrypt and secure session cookies.
"""

import json
import logging
import os
import secrets
import string
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

import bcrypt
from pydantic import BaseModel, EmailStr, Field, field_validator

logger = logging.getLogger("talk2me_ui.auth")


class User(BaseModel):
    """User model for authentication."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password_hash: str
    role_id: str
    role_name: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True
    last_login: Optional[datetime] = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username format."""
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username must contain only letters, numbers, underscores, and hyphens")
        return v.lower()

    @field_validator("password_hash")
    @classmethod
    def validate_password_hash(cls, v: str) -> str:
        """Validate password hash format."""
        if not v.startswith("$2b$") and not v.startswith("$2a$"):
            raise ValueError("Invalid password hash format")
        return v


class Session(BaseModel):
    """Session model for user sessions."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    @property
    def is_expired(self) -> bool:
        """Check if session is expired."""
        return datetime.utcnow() > self.expires_at


class UserManager:
    """Manager for user data storage and operations."""

    def __init__(self, data_dir: Path):
        """Initialize user manager.

        Args:
            data_dir: Directory to store user data
        """
        self.data_dir = data_dir
        self.users_file = data_dir / "users.json"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._users: Dict[str, User] = {}
        self._load_users()

    def _load_users(self) -> None:
        """Load users from storage."""
        if self.users_file.exists():
            try:
                with open(self.users_file, "r") as f:
                    data = json.load(f)
                    for user_data in data.values():
                        user = User(**user_data)
                        self._users[user.id] = user
                        # Also index by username and email for lookup
                        self._users[user.username] = user
                        self._users[user.email] = user
                logger.info(f"Loaded {len(self._users) // 3} users from storage")
            except Exception as e:
                logger.error(f"Failed to load users: {e}")
                self._users = {}

    def _save_users(self) -> None:
        """Save users to storage."""
        try:
            # Only save users by ID to avoid duplicates
            users_by_id = {uid: user.model_dump() for uid, user in self._users.items()
                          if isinstance(uid, str) and len(uid) == 36}  # UUID length
            with open(self.users_file, "w") as f:
                json.dump(users_by_id, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save users: {e}")

    def create_user(self, username: str, email: str, password: str) -> User:
        """Create a new user.

        Args:
            username: Username
            email: Email address
            password: Plain text password

        Returns:
            Created user

        Raises:
            ValueError: If user already exists
        """
        if self.get_user_by_username(username):
            raise ValueError("Username already exists")
        if self.get_user_by_email(email):
            raise ValueError("Email already exists")

        password_hash = self._hash_password(password)
        user = User(
            username=username,
            email=email,
            password_hash=password_hash
        )

        self._users[user.id] = user
        self._users[user.username] = user
        self._users[user.email] = user
        self._save_users()

        logger.info(f"Created user: {username} ({email})")
        return user

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        return self._users.get(user_id)

    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        return self._users.get(username.lower())

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        return self._users.get(email.lower())

    def authenticate_user(self, username_or_email: str, password: str) -> Optional[User]:
        """Authenticate user with username/email and password.

        Args:
            username_or_email: Username or email
            password: Plain text password

        Returns:
            User if authentication successful, None otherwise
        """
        user = self.get_user_by_username(username_or_email) or self.get_user_by_email(username_or_email)
        if not user or not user.is_active:
            return None

        if not self._verify_password(password, user.password_hash):
            return None

        # Update last login
        user.last_login = datetime.utcnow()
        self._save_users()

        return user

    def update_user(self, user_id: str, **updates) -> Optional[User]:
        """Update user information."""
        user = self.get_user_by_id(user_id)
        if not user:
            return None

        for key, value in updates.items():
            if key == "password":
                user.password_hash = self._hash_password(value)
            elif hasattr(user, key):
                setattr(user, key, value)

        self._save_users()
        return user

    @staticmethod
    def _hash_password(password: str) -> str:
        """Hash password using bcrypt."""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    @staticmethod
    def _verify_password(password: str, hashed: str) -> bool:
        """Verify password against hash."""
        try:
            return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
        except ValueError:
            return False


class SessionManager:
    """Manager for session data storage and operations."""

    def __init__(self, data_dir: Path, session_timeout: int = 24 * 60 * 60):  # 24 hours
        """Initialize session manager.

        Args:
            data_dir: Directory to store session data
            session_timeout: Session timeout in seconds
        """
        self.data_dir = data_dir
        self.sessions_file = data_dir / "sessions.json"
        self.session_timeout = session_timeout
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._sessions: Dict[str, Session] = {}
        self._load_sessions()
        self._cleanup_expired_sessions()

    def _load_sessions(self) -> None:
        """Load sessions from storage."""
        if self.sessions_file.exists():
            try:
                with open(self.sessions_file, "r") as f:
                    data = json.load(f)
                    for session_data in data.values():
                        session = Session(**session_data)
                        if not session.is_expired:
                            self._sessions[session.id] = session
                logger.info(f"Loaded {len(self._sessions)} active sessions")
            except Exception as e:
                logger.error(f"Failed to load sessions: {e}")
                self._sessions = {}

    def _save_sessions(self) -> None:
        """Save sessions to storage."""
        try:
            sessions_data = {sid: session.model_dump() for sid, session in self._sessions.items()}
            with open(self.sessions_file, "w") as f:
                json.dump(sessions_data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save sessions: {e}")

    def _cleanup_expired_sessions(self) -> None:
        """Remove expired sessions."""
        expired = [sid for sid, session in self._sessions.items() if session.is_expired]
        for sid in expired:
            del self._sessions[sid]
        if expired:
            self._save_sessions()
            logger.info(f"Cleaned up {len(expired)} expired sessions")

    def create_session(self, user_id: str, ip_address: Optional[str] = None,
                      user_agent: Optional[str] = None) -> Session:
        """Create a new session for user.

        Args:
            user_id: User ID
            ip_address: Client IP address
            user_agent: Client user agent

        Returns:
            Created session
        """
        expires_at = datetime.utcnow() + timedelta(seconds=self.session_timeout)
        session = Session(
            user_id=user_id,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent
        )

        self._sessions[session.id] = session
        self._save_sessions()

        logger.info(f"Created session for user {user_id}")
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID."""
        session = self._sessions.get(session_id)
        if session and session.is_expired:
            self.delete_session(session_id)
            return None
        return session

    def get_user_sessions(self, user_id: str) -> list[Session]:
        """Get all active sessions for a user."""
        return [s for s in self._sessions.values() if s.user_id == user_id and not s.is_expired]

    def extend_session(self, session_id: str) -> Optional[Session]:
        """Extend session expiration."""
        session = self.get_session(session_id)
        if session:
            session.expires_at = datetime.utcnow() + timedelta(seconds=self.session_timeout)
            self._save_sessions()
        return session

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            self._save_sessions()
            logger.info(f"Deleted session {session_id}")
            return True
        return False

    def delete_user_sessions(self, user_id: str) -> int:
        """Delete all sessions for a user.

        Returns:
            Number of sessions deleted
        """
        user_sessions = [sid for sid, s in self._sessions.items() if s.user_id == user_id]
        for sid in user_sessions:
            del self._sessions[sid]
        if user_sessions:
            self._save_sessions()
            logger.info(f"Deleted {len(user_sessions)} sessions for user {user_id}")
        return len(user_sessions)


# Global instances
from .db_managers import db_user_manager, db_session_manager
user_manager = db_user_manager
session_manager = db_session_manager


def get_current_user(session_id: str) -> Optional[User]:
    """Get current user from session ID.

    Args:
        session_id: Session ID from cookie

    Returns:
        User if session is valid, None otherwise
    """
    session = session_manager.get_session(session_id)
    if not session:
        return None

    db_user = user_manager.get_user_by_id(session.user_id)
    if not db_user or not db_user.is_active:
        return None

    # Convert database model to pydantic model
    return User(
        id=db_user.id,
        username=db_user.username,
        email=db_user.email,
        password_hash=db_user.password_hash,
        role_id=db_user.role_id,
        role_name=db_user.role.name if db_user.role else None,
        created_at=db_user.created_at,
        is_active=db_user.is_active,
        last_login=db_user.last_login,
    )


def generate_session_cookie(session: Session) -> str:
    """Generate secure session cookie value."""
    return f"{session.id}.{secrets.token_hex(16)}"


def parse_session_cookie(cookie_value: str) -> Optional[str]:
    """Parse session ID from cookie value."""
    if "." not in cookie_value:
        return None
    return cookie_value.split(".")[0]
