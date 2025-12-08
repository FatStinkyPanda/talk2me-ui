"""Role-Based Access Control (RBAC) implementation for Talk2Me UI.

This module provides RBAC functionality including permission checking,
role management, and access control enforcement.
"""

import logging
from typing import List, Optional, Set

from .database import Permission, Role, RolePermission
from .db_managers import db_permission_manager, db_role_manager

logger = logging.getLogger(__name__)


class RBACManager:
    """Manager for role-based access control operations."""

    def __init__(self):
        self._role_permissions_cache = {}  # Cache role permissions for performance

    def check_permission(self, user_role_id: str, resource: str, action: str) -> bool:
        """Check if a user role has permission for a specific resource and action.

        Args:
            user_role_id: The user's role ID
            resource: Resource name (e.g., 'stt', 'tts', 'users')
            action: Action name (e.g., 'use', 'manage', 'view')

        Returns:
            True if the role has the permission, False otherwise
        """
        # Get permissions for this role
        permissions = self._get_role_permissions(user_role_id)

        # Check if the required permission exists
        required_permission = f"{resource}:{action}"
        return required_permission in permissions

    def check_any_permission(self, user_role_id: str, permissions: List[tuple]) -> bool:
        """Check if a user role has any of the specified permissions.

        Args:
            user_role_id: The user's role ID
            permissions: List of (resource, action) tuples

        Returns:
            True if the role has at least one of the permissions, False otherwise
        """
        role_permissions = self._get_role_permissions(user_role_id)

        for resource, action in permissions:
            if f"{resource}:{action}" in role_permissions:
                return True

        return False

    def _get_role_permissions(self, role_id: str) -> Set[str]:
        """Get all permissions for a role, with caching.

        Args:
            role_id: Role ID

        Returns:
            Set of permission strings in format "resource:action"
        """
        if role_id not in self._role_permissions_cache:
            permissions = db_role_manager.get_role_permissions(role_id)
            permission_set = {f"{p.resource}:{p.action}" for p in permissions}
            self._role_permissions_cache[role_id] = permission_set

        return self._role_permissions_cache[role_id]

    def clear_cache(self):
        """Clear the permission cache. Call this after role/permission changes."""
        self._role_permissions_cache.clear()

    def initialize_default_roles_and_permissions(self):
        """Initialize default roles and permissions in the database."""
        logger.info("Initializing default RBAC roles and permissions")

        # Define default permissions
        default_permissions = [
            # STT permissions
            ("stt", "use", "Use speech-to-text functionality"),

            # TTS permissions
            ("tts", "use", "Use text-to-speech functionality"),

            # Audiobook permissions
            ("audiobook", "use", "Use audiobook generation functionality"),

            # Voice permissions
            ("voices", "view", "View available voices"),
            ("voices", "manage_own", "Manage own voices"),
            ("voices", "manage_all", "Manage all voices"),

            # Sound permissions
            ("sounds", "view", "View available sounds"),
            ("sounds", "upload", "Upload sound files"),
            ("sounds", "manage_own", "Manage own sounds"),
            ("sounds", "manage_all", "Manage all sounds"),

            # User permissions
            ("users", "view", "View user information"),
            ("users", "manage", "Manage users"),

            # Role permissions
            ("roles", "view", "View roles and permissions"),
            ("roles", "manage", "Manage roles and permissions"),

            # Plugin permissions
            ("plugins", "view", "View plugins"),
            ("plugins", "manage", "Manage plugins"),

            # System permissions
            ("system", "admin", "Full system administration"),
            ("system", "view", "View system information"),

            # Conversation permissions
            ("conversation", "use", "Use real-time conversation"),
        ]

        # Create permissions
        created_permissions = {}
        for resource, action, description in default_permissions:
            permission_name = f"{resource}:{action}"
            try:
                permission = db_permission_manager.create_permission(
                    name=permission_name,
                    resource=resource,
                    action=action,
                    description=description
                )
                created_permissions[permission_name] = permission
                logger.debug(f"Created permission: {permission_name}")
            except ValueError:
                # Permission already exists
                permission = db_permission_manager.get_permission_by_name(permission_name)
                created_permissions[permission_name] = permission

        # Define default roles and their permissions
        default_roles = {
            "admin": {
                "description": "Full system administrator with all permissions",
                "permissions": [
                    "stt:use", "tts:use", "audiobook:use",
                    "voices:view", "voices:manage_own", "voices:manage_all",
                    "sounds:view", "sounds:upload", "sounds:manage_own", "sounds:manage_all",
                    "users:view", "users:manage",
                    "roles:view", "roles:manage",
                    "plugins:view", "plugins:manage",
                    "system:admin", "system:view",
                    "conversation:use"
                ]
            },
            "user": {
                "description": "Regular user with basic functionality",
                "permissions": [
                    "stt:use", "tts:use", "audiobook:use",
                    "voices:view", "voices:manage_own",
                    "sounds:view", "sounds:upload", "sounds:manage_own",
                    "system:view",
                    "conversation:use"
                ]
            },
            "guest": {
                "description": "Limited access user",
                "permissions": [
                    "stt:use", "tts:use",
                    "voices:view",
                    "sounds:view",
                    "system:view"
                ]
            }
        }

        # Create roles and assign permissions
        for role_name, role_data in default_roles.items():
            try:
                role = db_role_manager.create_role(
                    name=role_name,
                    description=role_data["description"]
                )
                logger.debug(f"Created role: {role_name}")

                # Assign permissions to role
                for permission_name in role_data["permissions"]:
                    if permission_name in created_permissions:
                        db_role_manager.assign_permission_to_role(
                            role.id,
                            created_permissions[permission_name].id
                        )
                        logger.debug(f"Assigned {permission_name} to {role_name}")

            except ValueError:
                # Role already exists
                role = db_role_manager.get_role_by_name(role_name)
                logger.debug(f"Role {role_name} already exists")

        logger.info("RBAC initialization completed")


# Global RBAC manager instance
rbac_manager = RBACManager()


def check_user_permission(user, resource: str, action: str) -> bool:
    """Check if a user has permission for a resource and action.

    Args:
        user: User object (from get_current_user)
        resource: Resource name
        action: Action name

    Returns:
        True if user has permission, False otherwise
    """
    if not user or not hasattr(user, 'role_id'):
        return False

    return rbac_manager.check_permission(user.role_id, resource, action)


def require_permission(resource: str, action: str):
    """Decorator to require specific permission for a route.

    Usage:
        @app.get("/admin")
        @require_permission("system", "admin")
        async def admin_route():
            pass
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract request from args/kwargs
            request = None
            for arg in args:
                if hasattr(arg, 'state') and hasattr(arg.state, 'user'):
                    request = arg
                    break

            if not request:
                # Try to find in kwargs
                request = kwargs.get('request')

            if not request:
                from fastapi import HTTPException
                raise HTTPException(status_code=500, detail="Request object not found")

            user = getattr(request.state, 'user', None)
            if not user:
                from fastapi import HTTPException
                raise HTTPException(status_code=401, detail="Authentication required")

            if not check_user_permission(user, resource, action):
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=403,
                    detail=f"Permission denied: {resource}:{action}"
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator
