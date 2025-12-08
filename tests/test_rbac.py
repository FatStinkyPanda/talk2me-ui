"""Tests for Role-Based Access Control (RBAC) functionality."""

from unittest.mock import Mock, patch

import pytest

from talk2me_ui.auth import User
from talk2me_ui.rbac import RBACManager, check_user_permission, require_permission


class TestRBACManager:
    """Test RBAC manager functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.rbac = RBACManager()

    def test_check_permission_admin_role(self):
        """Test permission checking for admin role."""
        # Mock admin role with full permissions
        with patch.object(
            self.rbac, "_get_role_permissions", return_value={"stt:use", "system:admin"}
        ):
            assert self.rbac.check_permission("admin-role-id", "stt", "use") is True
            assert self.rbac.check_permission("admin-role-id", "system", "admin") is True
            assert self.rbac.check_permission("admin-role-id", "invalid", "permission") is False

    def test_check_permission_user_role(self):
        """Test permission checking for user role."""
        # Mock user role with limited permissions
        with patch.object(self.rbac, "_get_role_permissions", return_value={"stt:use", "tts:use"}):
            assert self.rbac.check_permission("user-role-id", "stt", "use") is True
            assert self.rbac.check_permission("user-role-id", "tts", "use") is True
            assert self.rbac.check_permission("user-role-id", "system", "admin") is False

    def test_check_any_permission(self):
        """Test checking multiple permissions."""
        with patch.object(self.rbac, "_get_role_permissions", return_value={"stt:use", "tts:use"}):
            # Test with permissions user has
            assert (
                self.rbac.check_any_permission("user-role-id", [("stt", "use"), ("tts", "use")])
                is True
            )
            # Test with mixed permissions
            assert (
                self.rbac.check_any_permission(
                    "user-role-id", [("stt", "use"), ("system", "admin")]
                )
                is True
            )
            # Test with no matching permissions
            assert (
                self.rbac.check_any_permission(
                    "user-role-id", [("system", "admin"), ("roles", "manage")]
                )
                is False
            )

    def test_clear_cache(self):
        """Test cache clearing."""
        self.rbac._role_permissions_cache = {"test": {"cached": "permissions"}}
        self.rbac.clear_cache()
        assert self.rbac._role_permissions_cache == {}


class TestPermissionChecking:
    """Test permission checking utilities."""

    def test_check_user_permission_with_valid_user(self):
        """Test permission checking with valid user."""
        # Use a valid bcrypt hash format
        valid_hash = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewfBPjYQmHqXaXcO"
        user = User(
            id="test-user",
            username="testuser",
            email="test@example.com",
            password_hash=valid_hash,
            role_id="user-role-id",
        )

        with patch("talk2me_ui.rbac.rbac_manager") as mock_rbac:
            mock_rbac.check_permission.return_value = True
            assert check_user_permission(user, "stt", "use") is True
            mock_rbac.check_permission.assert_called_once_with("user-role-id", "stt", "use")

    def test_check_user_permission_with_invalid_user(self):
        """Test permission checking with invalid user."""
        assert check_user_permission(None, "stt", "use") is False

        # Test user without role_id attribute
        class MockUser:
            pass

        user_no_role = MockUser()
        assert check_user_permission(user_no_role, "stt", "use") is False


class TestRequirePermissionDecorator:
    """Test the require_permission decorator."""

    def test_require_permission_granted(self):
        """Test decorator when permission is granted."""
        mock_request = Mock()
        mock_user = Mock()
        mock_user.role_id = "admin-role"
        mock_request.state.user = mock_user
        mock_request.method = "GET"
        mock_request.url.path = "/test"

        @require_permission("stt", "use")
        async def test_function(request):
            return {"success": True}

        with patch("talk2me_ui.rbac.rbac_manager") as mock_rbac:
            mock_rbac.check_permission.return_value = True

            import asyncio

            result = asyncio.run(test_function(mock_request))
            assert result == {"success": True}

    def test_require_permission_denied(self):
        """Test decorator when permission is denied."""
        mock_request = Mock()
        mock_user = Mock()
        mock_user.role_id = "user-role"
        mock_request.state.user = mock_user
        mock_request.method = "GET"
        mock_request.url.path = "/test"

        @require_permission("system", "admin")
        async def test_function(request):
            return {"success": True}

        with patch("talk2me_ui.rbac.rbac_manager") as mock_rbac:
            mock_rbac.check_permission.return_value = False

            import asyncio

            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                asyncio.run(test_function(mock_request))

            assert exc_info.value.status_code == 403
            assert "Permission denied" in exc_info.value.detail

    def test_require_permission_no_user(self):
        """Test decorator when no user is authenticated."""
        mock_request = Mock()
        mock_request.state.user = None
        mock_request.method = "GET"
        mock_request.url.path = "/test"

        @require_permission("stt", "use")
        async def test_function(request):
            return {"success": True}

        import asyncio

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(test_function(mock_request))

        assert exc_info.value.status_code == 401


class TestRBACInitialization:
    """Test RBAC system initialization."""

    def test_initialize_default_roles_and_permissions(self):
        """Test initialization of default roles and permissions."""
        rbac = RBACManager()

        with (
            patch("talk2me_ui.rbac.db_permission_manager") as mock_perm_mgr,
            patch("talk2me_ui.rbac.db_role_manager") as mock_role_mgr,
        ):
            # Mock permission creation
            def mock_create_permission(name, resource, action, description=None):
                return Mock(id="perm-id", name=name)

            mock_perm_mgr.create_permission.side_effect = mock_create_permission
            mock_perm_mgr.get_permission_by_name.return_value = None

            # Mock role creation
            def mock_create_role(name, description=None):
                return Mock(id="role-id", name=name)

            mock_role_mgr.create_role.side_effect = mock_create_role
            mock_role_mgr.get_role_by_name.return_value = None

            # Mock permission assignment
            mock_role_mgr.assign_permission_to_role.return_value = Mock()

            rbac.initialize_default_roles_and_permissions()

            # Verify roles were created
            assert mock_role_mgr.create_role.call_count == 3  # admin, user, guest

            # Verify permissions were assigned
            assert mock_role_mgr.assign_permission_to_role.call_count > 0
