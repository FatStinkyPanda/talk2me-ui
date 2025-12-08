"""Database managers for Talk2Me UI.

This module provides database-backed managers that replace the file-based storage
with SQLAlchemy database operations.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from .database import (
    SessionLocal,
    User as DBUser,
    Session as DBSession,
    Role,
    Permission,
    RolePermission,
    Project,
    Sound,
    Voice,
    ConversationSession,
    Message,
)

logger = logging.getLogger(__name__)


class DatabaseUserManager:
    """Database-backed user manager."""

    def create_user(self, username: str, email: str, password: str, role_id: str = None) -> DBUser:
        """Create a new user."""
        db = SessionLocal()
        try:
            # Check if user exists
            if db.query(DBUser).filter(
                (DBUser.username == username) | (DBUser.email == email)
            ).first():
                raise ValueError("Username or email already exists")

            # Hash password
            from .auth import UserManager as FileUserManager
            password_hash = FileUserManager._hash_password(password)

            # Default to 'user' role if not specified
            if role_id is None:
                user_role = db.query(Role).filter(Role.name == "user").first()
                if not user_role:
                    raise ValueError("Default 'user' role not found. Please initialize roles first.")
                role_id = user_role.id

            user = DBUser(
                id=str(uuid4()),
                username=username,
                email=email,
                password_hash=password_hash,
                role_id=role_id,
            )

            db.add(user)
            db.commit()
            db.refresh(user)

            logger.info(f"Created user: {username}")
            return user

        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()

    def get_user_by_id(self, user_id: str) -> Optional[DBUser]:
        """Get user by ID."""
        db = SessionLocal()
        try:
            return db.query(DBUser).filter(DBUser.id == user_id).first()
        finally:
            db.close()

    def get_user_by_username(self, username: str) -> Optional[DBUser]:
        """Get user by username."""
        db = SessionLocal()
        try:
            return db.query(DBUser).filter(DBUser.username == username).first()
        finally:
            db.close()

    def get_user_by_email(self, email: str) -> Optional[DBUser]:
        """Get user by email."""
        db = SessionLocal()
        try:
            return db.query(DBUser).filter(DBUser.email == email).first()
        finally:
            db.close()

    def authenticate_user(self, username_or_email: str, password: str) -> Optional[DBUser]:
        """Authenticate user."""
        db = SessionLocal()
        try:
            user = db.query(DBUser).filter(
                (DBUser.username == username_or_email) | (DBUser.email == email)
            ).first()

            if not user or not user.is_active:
                return None

            # Verify password
            from .auth import UserManager as FileUserManager
            if not FileUserManager._verify_password(password, user.password_hash):
                return None

            # Update last login
            user.last_login = datetime.utcnow()
            db.commit()

            return user

        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()

    def update_user(self, user_id: str, **updates) -> Optional[DBUser]:
        """Update user information."""
        db = SessionLocal()
        try:
            user = db.query(DBUser).filter(DBUser.id == user_id).first()
            if not user:
                return None

            for key, value in updates.items():
                if key == "password":
                    from .auth import UserManager as FileUserManager
                    value = FileUserManager._hash_password(value)
                    key = "password_hash"
                if hasattr(user, key):
                    setattr(user, key, value)

            db.commit()
            db.refresh(user)
            return user

        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()


class DatabaseSessionManager:
    """Database-backed session manager."""

    def __init__(self, session_timeout: int = 24 * 60 * 60):
        self.session_timeout = session_timeout

    def create_session(self, user_id: str, ip_address: Optional[str] = None,
                      user_agent: Optional[str] = None) -> DBSession:
        """Create a new session."""
        db = SessionLocal()
        try:
            expires_at = datetime.utcnow() + timedelta(seconds=self.session_timeout)
            session = DBSession(
                id=str(uuid4()),
                user_id=user_id,
                expires_at=expires_at,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            db.add(session)
            db.commit()
            db.refresh(session)

            logger.info(f"Created session for user {user_id}")
            return session

        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()

    def get_session(self, session_id: str) -> Optional[DBSession]:
        """Get session by ID."""
        db = SessionLocal()
        try:
            session = db.query(DBSession).filter(DBSession.id == session_id).first()
            if session and session.is_expired:
                db.delete(session)
                db.commit()
                return None
            return session
        finally:
            db.close()

    def get_user_sessions(self, user_id: str) -> List[DBSession]:
        """Get all active sessions for a user."""
        db = SessionLocal()
        try:
            return db.query(DBSession).filter(
                DBSession.user_id == user_id,
                DBSession.expires_at > datetime.utcnow()
            ).all()
        finally:
            db.close()

    def extend_session(self, session_id: str) -> Optional[DBSession]:
        """Extend session expiration."""
        db = SessionLocal()
        try:
            session = db.query(DBSession).filter(DBSession.id == session_id).first()
            if session:
                session.expires_at = datetime.utcnow() + timedelta(seconds=self.session_timeout)
                db.commit()
                db.refresh(session)
            return session
        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        db = SessionLocal()
        try:
            session = db.query(DBSession).filter(DBSession.id == session_id).first()
            if session:
                db.delete(session)
                db.commit()
                logger.info(f"Deleted session {session_id}")
                return True
            return False
        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()

    def delete_user_sessions(self, user_id: str) -> int:
        """Delete all sessions for a user."""
        db = SessionLocal()
        try:
            sessions = db.query(DBSession).filter(DBSession.user_id == user_id).all()
            count = len(sessions)
            for session in sessions:
                db.delete(session)
            db.commit()
            if count:
                logger.info(f"Deleted {count} sessions for user {user_id}")
            return count
        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()


class DatabaseSoundManager:
    """Database-backed sound manager."""

    def create_sound(self, sound_data: dict, user_id: str) -> Sound:
        """Create a new sound."""
        db = SessionLocal()
        try:
            sound = Sound(
                id=sound_data.get("id", str(uuid4())),
                name=sound_data["name"],
                sound_type=sound_data["sound_type"],
                category=sound_data.get("category"),
                volume=sound_data.get("volume", 0.8),
                fade_in=sound_data.get("fade_in", 0.0),
                fade_out=sound_data.get("fade_out", 0.0),
                duration=sound_data.get("duration"),
                pause_speech=sound_data.get("pause_speech", False),
                loop=sound_data.get("loop", True),
                duck_level=sound_data.get("duck_level", 0.2),
                duck_speech=sound_data.get("duck_speech", True),
                filename=sound_data["filename"],
                original_filename=sound_data["original_filename"],
                content_type=sound_data["content_type"],
                size=sound_data["size"],
                user_id=user_id,
            )

            db.add(sound)
            db.commit()
            db.refresh(sound)

            logger.info(f"Created sound: {sound.name} ({sound.id})")
            return sound

        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()

    def get_sound(self, sound_id: str) -> Optional[Sound]:
        """Get sound by ID."""
        db = SessionLocal()
        try:
            return db.query(Sound).filter(Sound.id == sound_id).first()
        finally:
            db.close()

    def list_sounds(self, sound_type: Optional[str] = None, user_id: Optional[str] = None,
                   limit: int = 50, offset: int = 0) -> List[Sound]:
        """List sounds with optional filtering."""
        db = SessionLocal()
        try:
            query = db.query(Sound)
            if sound_type:
                query = query.filter(Sound.sound_type == sound_type)
            if user_id:
                query = query.filter(Sound.user_id == user_id)

            return query.offset(offset).limit(limit).all()
        finally:
            db.close()

    def update_sound(self, sound_id: str, **updates) -> Optional[Sound]:
        """Update sound metadata."""
        db = SessionLocal()
        try:
            sound = db.query(Sound).filter(Sound.id == sound_id).first()
            if not sound:
                return None

            for key, value in updates.items():
                if hasattr(sound, key):
                    setattr(sound, key, value)

            db.commit()
            db.refresh(sound)
            return sound

        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()

    def delete_sound(self, sound_id: str) -> bool:
        """Delete a sound."""
        db = SessionLocal()
        try:
            sound = db.query(Sound).filter(Sound.id == sound_id).first()
            if sound:
                db.delete(sound)
                db.commit()
                logger.info(f"Deleted sound: {sound.name} ({sound_id})")
                return True
            return False
        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()


class DatabaseRoleManager:
    """Database-backed role manager."""

    def create_role(self, name: str, description: str = None) -> Role:
        """Create a new role."""
        db = SessionLocal()
        try:
            # Check if role exists
            if db.query(Role).filter(Role.name == name).first():
                raise ValueError(f"Role '{name}' already exists")

            role = Role(
                id=str(uuid4()),
                name=name,
                description=description,
            )

            db.add(role)
            db.commit()
            db.refresh(role)

            logger.info(f"Created role: {name}")
            return role

        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()

    def get_role_by_id(self, role_id: str) -> Optional[Role]:
        """Get role by ID."""
        db = SessionLocal()
        try:
            return db.query(Role).filter(Role.id == role_id).first()
        finally:
            db.close()

    def get_role_by_name(self, name: str) -> Optional[Role]:
        """Get role by name."""
        db = SessionLocal()
        try:
            return db.query(Role).filter(Role.name == name).first()
        finally:
            db.close()

    def list_roles(self) -> List[Role]:
        """List all roles."""
        db = SessionLocal()
        try:
            return db.query(Role).all()
        finally:
            db.close()

    def assign_permission_to_role(self, role_id: str, permission_id: str) -> RolePermission:
        """Assign a permission to a role."""
        db = SessionLocal()
        try:
            # Check if assignment already exists
            existing = db.query(RolePermission).filter(
                RolePermission.role_id == role_id,
                RolePermission.permission_id == permission_id
            ).first()

            if existing:
                return existing

            role_permission = RolePermission(
                id=str(uuid4()),
                role_id=role_id,
                permission_id=permission_id,
            )

            db.add(role_permission)
            db.commit()
            db.refresh(role_permission)

            logger.info(f"Assigned permission {permission_id} to role {role_id}")
            return role_permission

        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()

    def remove_permission_from_role(self, role_id: str, permission_id: str) -> bool:
        """Remove a permission from a role."""
        db = SessionLocal()
        try:
            role_permission = db.query(RolePermission).filter(
                RolePermission.role_id == role_id,
                RolePermission.permission_id == permission_id
            ).first()

            if role_permission:
                db.delete(role_permission)
                db.commit()
                logger.info(f"Removed permission {permission_id} from role {role_id}")
                return True
            return False

        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()

    def get_role_permissions(self, role_id: str) -> List[Permission]:
        """Get all permissions for a role."""
        db = SessionLocal()
        try:
            role_permissions = db.query(RolePermission).filter(
                RolePermission.role_id == role_id
            ).all()

            permission_ids = [rp.permission_id for rp in role_permissions]
            if permission_ids:
                return db.query(Permission).filter(Permission.id.in_(permission_ids)).all()
            return []

        finally:
            db.close()


class DatabasePermissionManager:
    """Database-backed permission manager."""

    def create_permission(self, name: str, resource: str, action: str, description: str = None) -> Permission:
        """Create a new permission."""
        db = SessionLocal()
        try:
            # Check if permission exists
            if db.query(Permission).filter(Permission.name == name).first():
                raise ValueError(f"Permission '{name}' already exists")

            permission = Permission(
                id=str(uuid4()),
                name=name,
                resource=resource,
                action=action,
                description=description,
            )

            db.add(permission)
            db.commit()
            db.refresh(permission)

            logger.info(f"Created permission: {name}")
            return permission

        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()

    def get_permission_by_id(self, permission_id: str) -> Optional[Permission]:
        """Get permission by ID."""
        db = SessionLocal()
        try:
            return db.query(Permission).filter(Permission.id == permission_id).first()
        finally:
            db.close()

    def get_permission_by_name(self, name: str) -> Optional[Permission]:
        """Get permission by name."""
        db = SessionLocal()
        try:
            return db.query(Permission).filter(Permission.name == name).first()
        finally:
            db.close()

    def list_permissions(self) -> List[Permission]:
        """List all permissions."""
        db = SessionLocal()
        try:
            return db.query(Permission).all()
        finally:
            db.close()

    def list_permissions_by_resource(self, resource: str) -> List[Permission]:
        """List permissions for a specific resource."""
        db = SessionLocal()
        try:
            return db.query(Permission).filter(Permission.resource == resource).all()
        finally:
            db.close()


# Global instances
db_user_manager = DatabaseUserManager()
db_session_manager = DatabaseSessionManager()
db_sound_manager = DatabaseSoundManager()
db_role_manager = DatabaseRoleManager()
db_permission_manager = DatabasePermissionManager()
