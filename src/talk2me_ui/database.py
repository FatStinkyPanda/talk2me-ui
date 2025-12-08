"""Database models and configuration for Talk2Me UI.

This module provides SQLAlchemy models for all application data,
database initialization, and session management.
"""

import os
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

Base = declarative_base()

# Database URL - defaults to SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/talk2me.db")

# Create engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    echo=False,  # Set to True for SQL debugging
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Role(Base):
    """Role model for role-based access control."""

    __tablename__ = "roles"

    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(50), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    users = relationship("User", back_populates="role")
    role_permissions = relationship("RolePermission", back_populates="role")


class Permission(Base):
    """Permission model for role-based access control."""

    __tablename__ = "permissions"

    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    resource = Column(String(50), nullable=False)  # e.g., 'stt', 'tts', 'users'
    action = Column(String(50), nullable=False)  # e.g., 'use', 'manage', 'view'
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    role_permissions = relationship("RolePermission", back_populates="permission")


class RolePermission(Base):
    """Many-to-many relationship between roles and permissions."""

    __tablename__ = "role_permissions"

    id = Column(String(36), primary_key=True, index=True)
    role_id = Column(String(36), ForeignKey("roles.id"), nullable=False)
    permission_id = Column(String(36), ForeignKey("permissions.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    role = relationship("Role", back_populates="role_permissions")
    permission = relationship("Permission", back_populates="role_permissions")


class User(Base):
    """User model for authentication and user management."""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role_id = Column(String(36), ForeignKey("roles.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    last_login = Column(DateTime, nullable=True)

    # Relationships
    role = relationship("Role", back_populates="users")
    sessions = relationship("Session", back_populates="user")
    projects = relationship("Project", back_populates="user")
    voices = relationship("Voice", back_populates="user")
    sounds = relationship("Sound", back_populates="user")
    conversation_sessions = relationship("ConversationSession", back_populates="user")


class Session(Base):
    """User session model for authentication."""

    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    ip_address = Column(String(45), nullable=True)  # IPv6 support
    user_agent = Column(Text, nullable=True)

    # Relationships
    user = relationship("User", back_populates="sessions")


class Project(Base):
    """Project model for organizing work."""

    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    # Relationships
    user = relationship("User", back_populates="projects")


class Voice(Base):
    """Voice model for TTS voice profiles."""

    __tablename__ = "voices"

    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    language = Column(String(10), default="en", nullable=False)
    api_voice_id = Column(String(255), nullable=True)  # External API voice ID
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    # Relationships
    user = relationship("User", back_populates="voices")


class Sound(Base):
    """Sound model for sound effects and background audio."""

    __tablename__ = "sounds"

    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    sound_type = Column(String(20), nullable=False)  # 'effect' or 'background'
    category = Column(String(100), nullable=True)
    volume = Column(Float, default=0.8, nullable=False)
    fade_in = Column(Float, default=0.0, nullable=False)
    fade_out = Column(Float, default=0.0, nullable=False)
    duration = Column(Float, nullable=True)  # For effects
    pause_speech = Column(Boolean, default=False, nullable=False)  # For effects
    loop = Column(Boolean, default=True, nullable=False)  # For background
    duck_level = Column(Float, default=0.2, nullable=False)  # For background
    duck_speech = Column(Boolean, default=True, nullable=False)  # For background
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False)
    size = Column(Integer, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    # Relationships
    user = relationship("User", back_populates="sounds")


class ConversationSession(Base):
    """Conversation session model for chat/conversation tracking."""

    __tablename__ = "conversation_sessions"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    title = Column(String(255), nullable=True)  # Optional session title

    # Relationships
    user = relationship("User", back_populates="conversation_sessions")
    messages = relationship("Message", back_populates="session")


class Message(Base):
    """Message model for conversation messages."""

    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, index=True)
    session_id = Column(String(36), ForeignKey("conversation_sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    message_metadata = Column(Text, nullable=True)  # JSON metadata

    # Relationships
    session = relationship("ConversationSession", back_populates="messages")


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database and create all tables."""
    Base.metadata.create_all(bind=engine)


def reset_db():
    """Drop all tables and recreate them. USE WITH CAUTION!"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
