#!/usr/bin/env python3
"""Migration script to move existing JSON data to SQLite database.

This script migrates users, sessions, projects, voices, sounds, and other
file-based data to the new database schema.
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from talk2me_ui.database import (
    Project,
    Session,
    SessionLocal,
    Sound,
    User,
    init_db,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_users():
    """Migrate user data from JSON to database."""
    users_file = Path("data/users/users.json")
    if not users_file.exists():
        logger.info("No users file found, skipping user migration")
        return

    db = SessionLocal()
    try:
        with open(users_file) as f:
            users_data = json.load(f)

        for user_data in users_data.values():
            # Check if user already exists
            existing = db.query(User).filter(User.username == user_data["username"]).first()
            if existing:
                logger.info(f"User {user_data['username']} already exists, skipping")
                continue

            user = User(
                id=user_data["id"],
                username=user_data["username"],
                email=user_data["email"],
                password_hash=user_data["password_hash"],
                created_at=datetime.fromisoformat(user_data["created_at"])
                if "created_at" in user_data
                else datetime.utcnow(),
                is_active=user_data.get("is_active", True),
                last_login=datetime.fromisoformat(user_data["last_login"])
                if user_data.get("last_login")
                else None,
            )
            db.add(user)
            logger.info(f"Migrated user: {user.username}")

        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to migrate users: {e}")
    finally:
        db.close()


def migrate_sessions():
    """Migrate session data from JSON to database."""
    sessions_file = Path("data/sessions/sessions.json")
    if not sessions_file.exists():
        logger.info("No sessions file found, skipping session migration")
        return

    db = SessionLocal()
    try:
        with open(sessions_file) as f:
            sessions_data = json.load(f)

        for session_data in sessions_data.values():
            # Check if session already exists
            existing = db.query(Session).filter(Session.id == session_data["id"]).first()
            if existing:
                logger.info(f"Session {session_data['id']} already exists, skipping")
                continue

            session = Session(
                id=session_data["id"],
                user_id=session_data["user_id"],
                created_at=datetime.fromisoformat(session_data["created_at"]),
                expires_at=datetime.fromisoformat(session_data["expires_at"]),
                ip_address=session_data.get("ip_address"),
                user_agent=session_data.get("user_agent"),
            )
            db.add(session)
            logger.info(f"Migrated session: {session.id}")

        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to migrate sessions: {e}")
    finally:
        db.close()


def migrate_projects():
    """Migrate project data from JSON files to database."""
    projects_dir = Path("data/projects")
    if not projects_dir.exists():
        logger.info("No projects directory found, skipping project migration")
        return

    db = SessionLocal()
    try:
        # Get or create default user
        default_user = db.query(User).first()
        if not default_user:
            default_user = User(
                id=str(uuid4()),
                username="default_user",
                email="default@example.com",
                password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewfLkIwF/4zqkPu",  # "password"
            )
            db.add(default_user)
            db.commit()
            logger.info("Created default user for migration")

        for json_file in projects_dir.glob("*.json"):
            with open(json_file) as f:
                project_data = json.load(f)

            # Check if project already exists
            existing = db.query(Project).filter(Project.id == json_file.stem).first()
            if existing:
                logger.info(f"Project {json_file.stem} already exists, skipping")
                continue

            project = Project(
                id=json_file.stem,
                name=project_data["name"],
                description=project_data.get("description", ""),
                user_id=project_data.get("user_id", default_user.id),
            )
            db.add(project)
            logger.info(f"Migrated project: {project.name}")

        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to migrate projects: {e}")
    finally:
        db.close()


def migrate_sounds():
    """Migrate sound effect and background audio data."""
    sfx_dir = Path("data/sfx")
    bg_dir = Path("data/background")

    db = SessionLocal()
    try:
        # Get or create default user
        default_user = db.query(User).first()
        if not default_user:
            default_user = User(
                id=str(uuid4()),
                username="default_user",
                email="default@example.com",
                password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewfLkIwF/4zqkPu",  # "password"
            )
            db.add(default_user)
            db.commit()
            logger.info("Created default user for migration")

        # Migrate sound effects
        if sfx_dir.exists():
            for json_file in sfx_dir.glob("*.json"):
                with open(json_file) as f:
                    sound_data = json.load(f)

                # Check if sound already exists
                existing = db.query(Sound).filter(Sound.id == sound_data["id"]).first()
                if existing:
                    logger.info(f"Sound {sound_data['id']} already exists, skipping")
                    continue

                # Parse uploaded_at safely
                uploaded_at = datetime.utcnow()
                if "uploaded_at" in sound_data and isinstance(sound_data["uploaded_at"], str):
                    try:
                        uploaded_at = datetime.fromisoformat(sound_data["uploaded_at"])
                    except ValueError:
                        # Handle invalid date formats
                        uploaded_at = datetime.utcnow()

                sound = Sound(
                    id=sound_data["id"],
                    name=sound_data["name"],
                    sound_type="effect",
                    category=sound_data.get("category"),
                    volume=sound_data.get("volume", 0.8),
                    fade_in=sound_data.get("fade_in", 0.0),
                    fade_out=sound_data.get("fade_out", 0.0),
                    duration=sound_data.get("duration"),
                    pause_speech=sound_data.get("pause_speech", False),
                    filename=sound_data["filename"],
                    original_filename=sound_data.get("original_filename", sound_data["filename"]),
                    content_type=sound_data.get("content_type", "audio/wav"),
                    size=sound_data.get("size", 0),
                    uploaded_at=uploaded_at,
                    user_id=sound_data.get("user_id", default_user.id),
                )
                db.add(sound)
                logger.info(f"Migrated sound effect: {sound.name}")

        # Migrate background audio
        if bg_dir.exists():
            for json_file in bg_dir.glob("*.json"):
                with open(json_file) as f:
                    sound_data = json.load(f)

                # Check if sound already exists
                existing = db.query(Sound).filter(Sound.id == sound_data["id"]).first()
                if existing:
                    logger.info(f"Sound {sound_data['id']} already exists, skipping")
                    continue

                # Parse uploaded_at safely
                uploaded_at = datetime.utcnow()
                if "uploaded_at" in sound_data and isinstance(sound_data["uploaded_at"], str):
                    try:
                        uploaded_at = datetime.fromisoformat(sound_data["uploaded_at"])
                    except ValueError:
                        # Handle invalid date formats
                        uploaded_at = datetime.utcnow()

                sound = Sound(
                    id=sound_data["id"],
                    name=sound_data["name"],
                    sound_type="background",
                    volume=sound_data.get("volume", 0.3),
                    fade_in=sound_data.get("fade_in", 1.0),
                    fade_out=sound_data.get("fade_out", 1.0),
                    duck_level=sound_data.get("duck_level", 0.2),
                    loop=sound_data.get("loop", True),
                    duck_speech=sound_data.get("duck_speech", True),
                    filename=sound_data["filename"],
                    original_filename=sound_data.get("original_filename", sound_data["filename"]),
                    content_type=sound_data.get("content_type", "audio/wav"),
                    size=sound_data.get("size", 0),
                    uploaded_at=uploaded_at,
                    user_id=sound_data.get("user_id", default_user.id),
                )
                db.add(sound)
                logger.info(f"Migrated background audio: {sound.name}")

        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to migrate sounds: {e}")
    finally:
        db.close()


def main():
    """Run the migration."""
    logger.info("Starting database migration...")

    # Initialize database
    init_db()

    # Run migrations
    migrate_users()
    migrate_sessions()
    migrate_projects()
    migrate_sounds()

    logger.info("Database migration completed!")


if __name__ == "__main__":
    main()
