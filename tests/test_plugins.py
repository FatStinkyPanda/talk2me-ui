"""Tests for the plugin system."""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from src.talk2me_ui.plugins.discovery import PluginDiscovery
from src.talk2me_ui.plugins.interfaces import (
    PluginContext,
    PluginInterface,
    PluginMetadata,
)
from src.talk2me_ui.plugins.lifecycle import PluginLifecycle
from src.talk2me_ui.plugins.marketplace import PluginMarketplace
from src.talk2me_ui.plugins.plugin_manager import PluginManager


class MockPlugin(PluginInterface):
    """Mock plugin for testing."""

    def __init__(self):
        self.initialized = False
        self.shutdown_called = False

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="test_plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test Author",
            plugin_type="audio_processor",
        )

    async def initialize(self, config):
        self.initialized = True
        self.config = config

    async def shutdown(self):
        self.shutdown_called = True

    def get_config_schema(self):
        return {"type": "object", "properties": {"enabled": {"type": "boolean", "default": True}}}


class TestPluginDiscovery:
    """Test plugin discovery functionality."""

    def setup_method(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.discovery = PluginDiscovery(self.temp_dir)

    def teardown_method(self):
        # Clean up temp directory
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_discover_plugins_empty_dir(self):
        """Test discovering plugins in empty directory."""
        result = asyncio.run(self.discovery.discover_plugins())
        assert result == []

    def test_discover_plugins_with_valid_plugin(self):
        """Test discovering plugins with valid plugin directory."""
        # Create plugin directory
        plugin_dir = self.temp_dir / "test_plugin"
        plugin_dir.mkdir()

        # Create plugin.json
        plugin_json = {
            "name": "test_plugin",
            "version": "1.0.0",
            "description": "Test plugin",
            "author": "Test Author",
            "type": "audio_processor",
        }

        with open(plugin_dir / "plugin.json", "w") as f:
            json.dump(plugin_json, f)

        # Create plugin file
        plugin_file = plugin_dir / "plugin.py"
        plugin_file.write_text("""
from src.talk2me_ui.plugins.interfaces import PluginInterface, PluginMetadata

class TestPlugin(PluginInterface):
    @property
    def metadata(self):
        return PluginMetadata(
            name="test_plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test Author",
            plugin_type="audio_processor",
        )

    async def initialize(self, config): pass
    async def shutdown(self): pass
    def get_config_schema(self): return {}
""")

        result = asyncio.run(self.discovery.discover_plugins())
        assert "test_plugin" in result

    def test_discover_plugins_with_invalid_plugin(self):
        """Test discovering plugins with invalid plugin directory."""
        # Create plugin directory without plugin.json
        plugin_dir = self.temp_dir / "invalid_plugin"
        plugin_dir.mkdir()

        result = asyncio.run(self.discovery.discover_plugins())
        assert "invalid_plugin" not in result

    def test_get_plugin_info(self):
        """Test getting plugin information."""
        # Create plugin directory
        plugin_dir = self.temp_dir / "test_plugin"
        plugin_dir.mkdir()

        plugin_json = {
            "name": "test_plugin",
            "version": "1.0.0",
            "description": "Test plugin",
            "author": "Test Author",
            "type": "audio_processor",
            "dependencies": ["dep1"],
            "tags": ["test"],
        }

        with open(plugin_dir / "plugin.json", "w") as f:
            json.dump(plugin_json, f)

        result = asyncio.run(self.discovery.get_plugin_info("test_plugin"))
        assert result is not None
        assert result["name"] == "test_plugin"
        assert result["version"] == "1.0.0"
        assert result["dependencies"] == ["dep1"]


class TestPluginLifecycle:
    """Test plugin lifecycle management."""

    def setup_method(self):
        self.lifecycle = PluginLifecycle()

    def test_activate_plugin_success(self):
        """Test successful plugin activation."""
        plugin = MockPlugin()

        result = asyncio.run(self.lifecycle.activate_plugin("test_plugin", plugin, None))

        assert result is True
        assert plugin.initialized is True
        assert self.lifecycle.is_plugin_active("test_plugin") is True

    def test_activate_plugin_failure(self):
        """Test plugin activation failure."""
        plugin = MockPlugin()

        # Make initialization fail
        async def failing_initialize(config):
            raise Exception("Initialization failed")

        plugin.initialize = failing_initialize

        result = asyncio.run(self.lifecycle.activate_plugin("test_plugin", plugin, None))

        assert result is False
        assert self.lifecycle.is_plugin_active("test_plugin") is False

    def test_deactivate_plugin_success(self):
        """Test successful plugin deactivation."""
        plugin = MockPlugin()

        # First activate
        asyncio.run(self.lifecycle.activate_plugin("test_plugin", plugin, None))

        # Then deactivate
        result = asyncio.run(self.lifecycle.deactivate_plugin("test_plugin", plugin))

        assert result is True
        assert plugin.shutdown_called is True
        assert self.lifecycle.is_plugin_active("test_plugin") is False

    def test_deactivate_plugin_failure(self):
        """Test plugin deactivation failure."""
        plugin = MockPlugin()

        # First activate
        asyncio.run(self.lifecycle.activate_plugin("test_plugin", plugin, None))

        # Make shutdown fail
        async def failing_shutdown():
            raise Exception("Shutdown failed")

        plugin.shutdown = failing_shutdown

        result = asyncio.run(self.lifecycle.deactivate_plugin("test_plugin", plugin))

        assert result is False
        # Should still be marked as inactive
        assert self.lifecycle.is_plugin_active("test_plugin") is False


class TestPluginManager:
    """Test plugin manager functionality."""

    def setup_method(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.context = Mock(spec=PluginContext)
        self.manager = PluginManager(self.temp_dir, self.context)

    def teardown_method(self):
        import shutil

        shutil.rmtree(self.temp_dir)

    @patch("src.talk2me_ui.plugins.plugin_manager.PluginDiscovery")
    @patch("src.talk2me_ui.plugins.plugin_manager.PluginLifecycle")
    async def test_initialize(self, mock_lifecycle_class, mock_discovery_class):
        """Test plugin manager initialization."""
        mock_discovery = Mock()
        mock_discovery.discover_plugins = AsyncMock(return_value=[])
        mock_discovery_class.return_value = mock_discovery

        mock_lifecycle = Mock()
        mock_lifecycle_class.return_value = mock_lifecycle

        await self.manager.initialize()

        mock_discovery.discover_plugins.assert_called_once()

    def test_get_plugin(self):
        """Test getting a plugin instance."""
        plugin = MockPlugin()
        self.manager.loaded_plugins["test_plugin"] = plugin

        result = self.manager.get_plugin("test_plugin")
        assert result is plugin

        result = self.manager.get_plugin("nonexistent")
        assert result is None

    def test_list_loaded_plugins(self):
        """Test listing loaded plugins."""
        self.manager.loaded_plugins["plugin1"] = MockPlugin()
        self.manager.loaded_plugins["plugin2"] = MockPlugin()

        result = self.manager.list_loaded_plugins()
        assert set(result) == {"plugin1", "plugin2"}


class TestPluginMarketplace:
    """Test plugin marketplace functionality."""

    def setup_method(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.marketplace = PluginMarketplace(
            marketplace_url="https://api.example.com", plugins_dir=self.temp_dir
        )

    def teardown_method(self):
        import shutil

        shutil.rmtree(self.temp_dir)

    @patch("aiohttp.ClientSession")
    async def test_list_available_plugins(self, mock_session_class):
        """Test listing available plugins from marketplace."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.json = AsyncMock(
            return_value={"plugins": [{"name": "test_plugin"}], "total": 1}
        )
        mock_response.status = 200
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session_class.return_value = mock_session

        await self.marketplace.initialize()

        result = await self.marketplace.list_available_plugins()

        assert result["plugins"] == [{"name": "test_plugin"}]
        assert result["total"] == 1

    @patch("aiohttp.ClientSession")
    async def test_install_plugin_success(self, mock_session_class):
        """Test successful plugin installation."""
        # Mock session and response
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=b"fake zip content")
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session_class.return_value = mock_session

        await self.marketplace.initialize()

        # Mock zipfile to avoid actual file operations
        with patch("zipfile.ZipFile") as mock_zip:
            mock_zip.return_value.__enter__ = Mock()
            mock_zip.return_value.__exit__ = Mock()
            mock_zip.return_value.extractall = Mock()

            result = await self.marketplace.install_plugin("test_plugin")

            assert result is True

    async def test_get_installed_plugins(self):
        """Test getting list of installed plugins."""
        # Create a plugin directory with metadata
        plugin_dir = self.temp_dir / "test_plugin"
        plugin_dir.mkdir()

        metadata = {
            "name": "test_plugin",
            "version": "1.0.0",
            "description": "Test plugin",
            "author": "Test Author",
            "type": "audio_processor",
        }

        with open(plugin_dir / "plugin.json", "w") as f:
            json.dump(metadata, f)

        result = await self.marketplace.get_installed_plugins()

        assert len(result) == 1
        assert result[0]["name"] == "test_plugin"
        assert result[0]["version"] == "1.0.0"

    async def test_uninstall_plugin(self):
        """Test plugin uninstallation."""
        # Create a plugin directory
        plugin_dir = self.temp_dir / "test_plugin"
        plugin_dir.mkdir()

        result = await self.marketplace.uninstall_plugin("test_plugin")

        assert result is True
        assert not plugin_dir.exists()

    async def test_uninstall_nonexistent_plugin(self):
        """Test uninstalling non-existent plugin."""
        result = await self.marketplace.uninstall_plugin("nonexistent")

        assert result is False


class TestPluginInterfaces:
    """Test plugin interface classes."""

    def test_plugin_metadata(self):
        """Test PluginMetadata class."""
        metadata = PluginMetadata(
            name="test_plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test Author",
            plugin_type="audio_processor",
            dependencies=["dep1"],
            homepage="https://example.com",
            license="MIT",
            tags=["test", "audio"],
        )

        assert metadata.name == "test_plugin"
        assert metadata.version == "1.0.0"
        assert metadata.dependencies == ["dep1"]
        assert metadata.tags == ["test", "audio"]

    def test_plugin_context(self):
        """Test PluginContext class."""
        context = PluginContext(
            app_config={"setting": "value"},
            database_manager=Mock(),
            api_client=Mock(),
            user_manager=Mock(),
            cache_manager=Mock(),
        )

        assert context.app_config["setting"] == "value"
        assert context.database_manager is not None
        assert context.api_client is not None


# Integration tests
class TestPluginSystemIntegration:
    """Integration tests for the complete plugin system."""

    def setup_method(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.context = Mock(spec=PluginContext)
        self.manager = PluginManager(self.temp_dir, self.context)

    def teardown_method(self):
        import shutil

        shutil.rmtree(self.temp_dir)

    async def test_load_plugin_success(self):
        """Test loading a plugin successfully."""
        # Create plugin directory structure
        plugin_dir = self.temp_dir / "test_plugin"
        plugin_dir.mkdir()

        # Create plugin.json
        plugin_json = {
            "name": "test_plugin",
            "version": "1.0.0",
            "description": "Test plugin",
            "author": "Test Author",
            "type": "audio_processor",
        }

        with open(plugin_dir / "plugin.json", "w") as f:
            json.dump(plugin_json, f)

        # Create plugin.py with a valid plugin class
        plugin_code = """
from src.talk2me_ui.plugins.interfaces import PluginInterface, PluginMetadata

class TestPlugin(PluginInterface):
    @property
    def metadata(self):
        return PluginMetadata(
            name="test_plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test Author",
            plugin_type="audio_processor",
        )

    async def initialize(self, config):
        self.initialized = True

    async def shutdown(self):
        self.shutdown_called = True

    def get_config_schema(self):
        return {"type": "object"}
"""

        with open(plugin_dir / "plugin.py", "w") as f:
            f.write(plugin_code)

        # Mock the _load_plugin_module to return our mock plugin
        original_load = self.manager._load_plugin_module

        async def mock_load(plugin_path, metadata):
            return MockPlugin()

        self.manager._load_plugin_module = mock_load

        try:
            result = await self.manager.load_plugin("test_plugin")
            assert result is True
            assert "test_plugin" in self.manager.loaded_plugins
        finally:
            self.manager._load_plugin_module = original_load

    async def test_load_plugin_with_dependencies(self):
        """Test loading a plugin with dependencies."""
        # Create dependency plugin
        dep_dir = self.temp_dir / "dependency_plugin"
        dep_dir.mkdir()

        dep_json = {
            "name": "dependency_plugin",
            "version": "1.0.0",
            "description": "Dependency plugin",
            "author": "Test Author",
            "type": "audio_processor",
        }

        with open(dep_dir / "plugin.json", "w") as f:
            json.dump(dep_json, f)

        # Create main plugin with dependency
        plugin_dir = self.temp_dir / "main_plugin"
        plugin_dir.mkdir()

        plugin_json = {
            "name": "main_plugin",
            "version": "1.0.0",
            "description": "Main plugin",
            "author": "Test Author",
            "type": "audio_processor",
            "dependencies": ["dependency_plugin"],
        }

        with open(plugin_dir / "plugin.json", "w") as f:
            json.dump(plugin_json, f)

        # Mock loading to return mock plugins
        original_load = self.manager._load_plugin_module
        call_count = 0

        async def mock_load(plugin_path, metadata):
            nonlocal call_count
            call_count += 1
            return MockPlugin()

        self.manager._load_plugin_module = mock_load

        try:
            # Should fail because dependency is not loaded
            result = await self.manager.load_plugin("main_plugin")
            assert result is False  # Dependency not satisfied

            # Load dependency first
            result = await self.manager.load_plugin("dependency_plugin")
            assert result is True

            # Now main plugin should load
            result = await self.manager.load_plugin("main_plugin")
            assert result is True

        finally:
            self.manager._load_plugin_module = original_load
