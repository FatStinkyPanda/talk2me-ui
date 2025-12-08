#!/usr/bin/env python3
"""Data migration script for Talk2Me UI.

This script migrates existing JSON-based data to the new SQLite database.
Run this script after setting up the database but before switching to database-backed storage.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import sessionmaker

# Add src to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from talk2me_ui.database import (
    SessionLocal,
    User,
    Session as DBSession,
    Project,
    Sound,
    ConversationSession,
    Message,
    engine,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_DIR = Path("data")


def migrate_users():
    """Migrate users from JSON to database."""
    users_file = DATA_DIR / "users" / "users.json"
    if not users_file.exists():
        logger.info("No users.json file found, skipping user migration")
        return

    logger.info("Migrating users...")

    db = SessionLocal()
    try:
        with open(users_file) as f:
            users_data = json.load(f)

        migrated_count = 0
        for user_data in users_data.values():
            # Check if user already exists
            existing = db.query(User).filter_by(id=user_data["id"]).first()
            if existing:
                logger.info(f"User {user_data['username']} already exists, skipping")
                continue

            # Convert datetime strings back to datetime objects
            created_at = user_data.get("created_at")
            last_login = user_data.get("last_login")

            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            if isinstance(last_login, str):
                last_login = datetime.fromisoformat(last_login.replace('Z', '+00:00'))

            user = User(
                id=user_data["id"],
                username=user_data["username"],
                email=user_data["email"],
                password_hash=user_data["password_hash"],
                created_at=created_at or datetime.utcnow(),
                is_active=user_data.get("is_active", True),
                last_login=last_login,
            )
            db.add(user)
            migrated_count += 1

        db.commit()
        logger.info(f"Migrated {migrated_count} users")

    except Exception as e:
        logger.error(f"Failed to migrate users: {e}")
        db.rollback()
    finally:
        db.close()


def migrate_sessions():
    """Migrate sessions from JSON to database."""
    sessions_file = DATA_DIR / "sessions" / "sessions.json"
    if not sessions_file.exists():
        logger.info("No sessions.json file found, skipping session migration")
        return

    logger.info("Migrating sessions...")

    db = SessionLocal()
    try:
        with open(sessions_file) as f:
            sessions_data = json.load(f)

        migrated_count = 0
        for session_data in sessions_data.values():
            # Check if session already exists
            existing = db.query(DBSession).filter_by(id=session_data["id"]).first()
            if existing:
                logger.info(f"Session {session_data['id']} already exists, skipping")
                continue

            # Convert datetime strings
            created_at = session_data.get("created_at")
            expires_at = session_data.get("expires_at")

            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))

            session = DBSession(
                id=session_data["id"],
                user_id=session_data["user_id"],
                created_at=created_at or datetime.utcnow(),
                expires_at=expires_at,
                ip_address=session_data.get("ip_address"),
                user_agent=session_data.get("user_agent"),
            )
            db.add(session)
            migrated_count += 1

        db.commit()
        logger.info(f"Migrated {migrated_count} sessions")

    except Exception as e:
        logger.error(f"Failed to migrate sessions: {e}")
        db.rollback()
    finally:
        db.close()


def migrate_projects():
    """Migrate projects from JSON to database."""
    projects_dir = DATA_DIR / "projects"
    if not projects_dir.exists():
        logger.info("No projects directory found, skipping project migration")
        return

    logger.info("Migrating projects...")

    db = SessionLocal()
    try:
        migrated_count = 0
        for json_file in projects_dir.glob("*.json"):
            try:
                with open(json_file) as f:
                    project_data = json.load(f)

                # Skip if already exists
                existing = db.query(Project).filter_by(
                    name=project_data["name"],
                    user_id="system"  # Default user for migrated projects
                ).first()
                if existing:
                    logger.info(f"Project {project_data['name']} already exists, skipping")
                    continue

                project = Project(
                    id=f"proj_{migrated_count + 1}",  # Generate ID
                    name=project_data["name"],
                    description=project_data.get("description"),
                    user_id="system",  # Default user
                )
                db.add(project)
                migrated_count += 1

            except Exception as e:
                logger.error(f"Failed to migrate project {json_file}: {e}")

        db.commit()
        logger.info(f"Migrated {migrated_count} projects")

    except Exception as e:
        logger.error(f"Failed to migrate projects: {e}")
        db.rollback()
    finally:
        db.close()


def migrate_sounds():
    """Migrate sounds (effects and background) from JSON to database."""
    sound_dirs = [
        ("sfx", "effect"),
        ("background", "background")
    ]

    db = SessionLocal()
    try:
        total_migrated = 0

        for dir_name, sound_type in sound_dirs:
            sound_dir = DATA_DIR / dir_name
            if not sound_dir.exists():
                continue

            logger.info(f"Migrating {sound_type} sounds...")

            for json_file in sound_dir.glob("*.json"):
                try:
                    with open(json_file) as f:
                        sound_data = json.load(f)

                    # Skip if already exists
                    existing = db.query(Sound).filter_by(id=sound_data["id"]).first()
                    if existing:
                        logger.info(f"Sound {sound_data['id']} already exists, skipping")
                        continue

                    # Convert uploaded_at
                    uploaded_at = sound_data.get("uploaded_at")
                    if isinstance(uploaded_at, str):
                        uploaded_at = datetime.fromisoformat(uploaded_at.replace('Z', '+00:00'))

                    sound = Sound(
                        id=sound_data["id"],
                        name=sound_data["name"],
                        sound_type=sound_type,
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
                        uploaded_at=uploaded_at or datetime.utcnow(),
                        user_id="system",  # Default user
                    )
                    db.add(sound)
                    total_migrated += 1

                except Exception as e:
                    logger.error(f"Failed to migrate sound {json_file}: {e}")

        db.commit()
        logger.info(f"Migrated {total_migrated} sounds")

    except Exception as e:
        logger.error(f"Failed to migrate sounds: {e}")
        db.rollback()
    finally:
        db.close()


def create_default_user():
    """Create a default system user if no users exist."""
    db = SessionLocal()
    try:
        # Check if any users exist
        user_count = db.query(User).count()
        if user_count == 0:
            logger.info("Creating default system user...")

            # Create a default admin user
            from talk2me_ui.auth import UserManager
            user_manager = UserManager(Path("data"))
            default_user = user_manager.create_user(
                username="admin",
                email="admin@talk2me.local",
                password="changeme123"
            )

            # Also add to database
            db_user = User(
                id=default_user.id,
                username=default_user.username,
                email=default_user.email,
                password_hash=default_user.password_hash,
                created_at=default_user.created_at,
                is_active=default_user.is_active,
                last_login=default_user.last_login,
            )
            db.add(db_user)
            db.commit()
            logger.info("Created default admin user: admin@talk2me.local / changeme123")
        else:
            logger.info("Users already exist, skipping default user creation")

    except Exception as e:
        logger.error(f"Failed to create default user: {e}")
        db.rollback()
    finally:
        db.close()


def main():
    """Run the migration process."""
    logger.info("Starting data migration to database...")

    # Create database tables if they don't exist
    from talk2me_ui.database import init_db
    init_db()

    # Run migrations
    create_default_user()
    migrate_users()
    migrate_sessions()
    migrate_projects()
    migrate_sounds()

    logger.info("Data migration completed!")


if __name__ == "__main__":
    main()
