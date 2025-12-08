"""Core plugin manager for loading and managing plugins."""

import asyncio
import importlib.util
import json
import logging
import sys
from pathlib import Path
from typing import Any

from .discovery import PluginDiscovery
from .interfaces import (
    APIEndpointPlugin,
    AudioProcessorPlugin,
    IntegrationPlugin,
    PluginContext,
    PluginInterface,
    PluginLoadContext,
    PluginMetadata,
    UIComponentPlugin,
)
from .lifecycle import PluginLifecycle

logger = logging.getLogger(__name__)


class PluginManager:
    """Central manager for plugin loading, lifecycle, and coordination."""

    def __init__(self, plugins_dir: Path, context: PluginContext):
        self.plugins_dir = plugins_dir
        self.context = context
        self.discovery = PluginDiscovery(plugins_dir)
        self.lifecycle = PluginLifecycle()

        # Plugin storage
        self.loaded_plugins: dict[str, PluginInterface] = {}
        self.plugin_configs: dict[str, dict[str, Any]] = {}
        self.plugin_metadata: dict[str, PluginMetadata] = {}

        # Plugin type registries
        self.audio_processors: dict[str, AudioProcessorPlugin] = {}
        self.ui_components: dict[str, UIComponentPlugin] = {}
        self.api_endpoints: dict[str, APIEndpointPlugin] = {}
        self.integrations: dict[str, IntegrationPlugin] = {}

        # Plugin dependencies
        self.plugin_dependencies: dict[str, list[str]] = {}
        self.reverse_dependencies: dict[str, list[str]] = {}

    async def initialize(self) -> None:
        """Initialize the plugin manager and load all available plugins."""
        logger.info("Initializing plugin manager")

        # Discover available plugins
        available_plugins = await self.discovery.discover_plugins()
        logger.info(f"Discovered {len(available_plugins)} plugins")

        # Load plugin configurations
        await self._load_plugin_configs()

        # Build dependency graph
        self._build_dependency_graph(available_plugins)

        # Load plugins in dependency order
        await self._load_plugins_in_order(available_plugins)

        logger.info(f"Successfully loaded {len(self.loaded_plugins)} plugins")

    async def shutdown(self) -> None:
        """Shutdown all loaded plugins."""
        logger.info("Shutting down plugin manager")

        # Shutdown plugins in reverse dependency order
        plugin_names = list(self.loaded_plugins.keys())
        plugin_names.reverse()

        for plugin_name in plugin_names:
            await self.lifecycle.deactivate_plugin(plugin_name, self.loaded_plugins[plugin_name])

        self.loaded_plugins.clear()
        self.audio_processors.clear()
        self.ui_components.clear()
        self.api_endpoints.clear()
        self.integrations.clear()

        logger.info("Plugin manager shutdown complete")

    async def load_plugin(self, plugin_name: str, config: dict[str, Any] | None = None) -> bool:
        """Load a specific plugin by name.

        Args:
            plugin_name: Name of the plugin to load
            config: Optional configuration override

        Returns:
            True if plugin loaded successfully
        """
        try:
            plugin_path = self.plugins_dir / plugin_name
            if not plugin_path.exists():
                logger.error(f"Plugin directory not found: {plugin_path}")
                return False

            # Load plugin metadata
            metadata = await self._load_plugin_metadata(plugin_path)
            if not metadata:
                return False

            # Check dependencies
            if not await self._check_dependencies(metadata):
                return False

            # Load plugin module
            plugin_instance = await self._load_plugin_module(plugin_path, metadata)
            if not plugin_instance:
                return False

            # Merge configuration
            plugin_config = self.plugin_configs.get(plugin_name, {})
            if config:
                plugin_config.update(config)

            # Initialize plugin
            load_context = PluginLoadContext(plugin_path, plugin_config, self.context)
            await self.lifecycle.activate_plugin(plugin_name, plugin_instance, load_context)

            # Register plugin in appropriate registries
            self._register_plugin(plugin_name, plugin_instance, metadata)

            logger.info(f"Successfully loaded plugin: {plugin_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_name}: {e}", exc_info=True)
            return False

    async def unload_plugin(self, plugin_name: str) -> bool:
        """Unload a specific plugin.

        Args:
            plugin_name: Name of the plugin to unload

        Returns:
            True if plugin unloaded successfully
        """
        if plugin_name not in self.loaded_plugins:
            logger.warning(f"Plugin not loaded: {plugin_name}")
            return False

        try:
            plugin_instance = self.loaded_plugins[plugin_name]

            # Check reverse dependencies
            if plugin_name in self.reverse_dependencies:
                dependents = self.reverse_dependencies[plugin_name]
                if dependents:
                    logger.error(
                        f"Cannot unload plugin {plugin_name}: still has dependents: {dependents}"
                    )
                    return False

            # Shutdown plugin
            await self.lifecycle.deactivate_plugin(plugin_name, plugin_instance)

            # Remove from registries
            self._unregister_plugin(plugin_name, plugin_instance)

            logger.info(f"Successfully unloaded plugin: {plugin_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to unload plugin {plugin_name}: {e}", exc_info=True)
            return False

    def get_plugin(self, plugin_name: str) -> PluginInterface | None:
        """Get a loaded plugin instance by name."""
        return self.loaded_plugins.get(plugin_name)

    def get_plugins_by_type(self, plugin_type: str) -> list[PluginInterface]:
        """Get all loaded plugins of a specific type."""
        if plugin_type == "audio_processor":
            return list(self.audio_processors.values())
        elif plugin_type == "ui_component":
            return list(self.ui_components.values())
        elif plugin_type == "api_endpoint":
            return list(self.api_endpoints.values())
        elif plugin_type == "integration":
            return list(self.integrations.values())
        else:
            return []

    def get_plugin_metadata(self, plugin_name: str) -> PluginMetadata | None:
        """Get metadata for a plugin."""
        return self.plugin_metadata.get(plugin_name)

    def list_loaded_plugins(self) -> list[str]:
        """List names of all loaded plugins."""
        return list(self.loaded_plugins.keys())

    async def _load_plugin_configs(self) -> None:
        """Load configuration for all plugins."""
        config_file = self.plugins_dir / "plugins.json"
        if config_file.exists():
            try:
                with open(config_file) as f:
                    self.plugin_configs = json.load(f)
                logger.info("Loaded plugin configurations")
            except Exception as e:
                logger.error(f"Failed to load plugin configurations: {e}")

    async def _load_plugin_metadata(self, plugin_path: Path) -> PluginMetadata | None:
        """Load metadata for a plugin."""
        metadata_file = plugin_path / "plugin.json"
        if not metadata_file.exists():
            logger.error(f"Plugin metadata file not found: {metadata_file}")
            return None

        try:
            with open(metadata_file) as f:
                metadata_dict = json.load(f)

            metadata = PluginMetadata(
                name=metadata_dict["name"],
                version=metadata_dict["version"],
                description=metadata_dict["description"],
                author=metadata_dict["author"],
                plugin_type=metadata_dict["type"],
                dependencies=metadata_dict.get("dependencies", []),
                config_schema=metadata_dict.get("config_schema", {}),
                homepage=metadata_dict.get("homepage"),
                license=metadata_dict.get("license"),
                tags=metadata_dict.get("tags", []),
            )

            return metadata

        except Exception as e:
            logger.error(f"Failed to load plugin metadata from {metadata_file}: {e}")
            return None

    async def _check_dependencies(self, metadata: PluginMetadata) -> bool:
        """Check if all dependencies for a plugin are satisfied."""
        for dep in metadata.dependencies:
            if dep not in self.loaded_plugins:
                logger.error(f"Plugin {metadata.name} missing dependency: {dep}")
                return False
        return True

    async def _load_plugin_module(
        self, plugin_path: Path, metadata: PluginMetadata
    ) -> PluginInterface | None:
        """Load a plugin module and instantiate the plugin class."""
        # Find the main plugin file
        plugin_file = None
        for file_path in plugin_path.glob("*.py"):
            if file_path.name != "__init__.py":
                plugin_file = file_path
                break

        if not plugin_file:
            logger.error(f"No plugin file found in {plugin_path}")
            return None

        try:
            # Load the module
            spec = importlib.util.spec_from_file_location(metadata.name, plugin_file)
            if not spec or not spec.loader:
                logger.error(f"Could not create module spec for {plugin_file}")
                return None

            module = importlib.util.module_from_spec(spec)
            sys.modules[metadata.name] = module
            spec.loader.exec_module(module)

            # Find the plugin class
            plugin_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, PluginInterface)
                    and attr != PluginInterface
                ):
                    plugin_class = attr
                    break

            if not plugin_class:
                logger.error(f"No plugin class found in {plugin_file}")
                return None

            # Instantiate the plugin
            plugin_instance = plugin_class()
            return plugin_instance

        except Exception as e:
            logger.error(f"Failed to load plugin module {plugin_file}: {e}", exc_info=True)
            return None

    def _build_dependency_graph(self, available_plugins: list[str]) -> None:
        """Build dependency graph for plugins."""
        # This is a simplified version - in production you'd use topological sort
        self.plugin_dependencies = {}
        self.reverse_dependencies = {}

        for plugin_name in available_plugins:
            plugin_path = self.plugins_dir / plugin_name
            metadata = asyncio.run(self._load_plugin_metadata(plugin_path))
            if metadata:
                self.plugin_dependencies[plugin_name] = metadata.dependencies
                for dep in metadata.dependencies:
                    if dep not in self.reverse_dependencies:
                        self.reverse_dependencies[dep] = []
                    self.reverse_dependencies[dep].append(plugin_name)

    async def _load_plugins_in_order(self, available_plugins: list[str]) -> None:
        """Load plugins in dependency order."""
        # Simplified loading - load all at once
        # In production, you'd implement topological sort
        for plugin_name in available_plugins:
            config = self.plugin_configs.get(plugin_name, {})
            await self.load_plugin(plugin_name, config)

    def _register_plugin(
        self, plugin_name: str, plugin_instance: PluginInterface, metadata: PluginMetadata
    ) -> None:
        """Register a plugin in the appropriate type registry."""
        self.loaded_plugins[plugin_name] = plugin_instance
        self.plugin_metadata[plugin_name] = metadata

        if isinstance(plugin_instance, AudioProcessorPlugin):
            self.audio_processors[plugin_name] = plugin_instance
        elif isinstance(plugin_instance, UIComponentPlugin):
            self.ui_components[plugin_name] = plugin_instance
        elif isinstance(plugin_instance, APIEndpointPlugin):
            self.api_endpoints[plugin_name] = plugin_instance
        elif isinstance(plugin_instance, IntegrationPlugin):
            self.integrations[plugin_name] = plugin_instance

    def _unregister_plugin(self, plugin_name: str, plugin_instance: PluginInterface) -> None:
        """Remove a plugin from type registries."""
        if plugin_name in self.loaded_plugins:
            del self.loaded_plugins[plugin_name]
        if plugin_name in self.plugin_metadata:
            del self.plugin_metadata[plugin_name]

        if isinstance(plugin_instance, AudioProcessorPlugin):
            self.audio_processors.pop(plugin_name, None)
        elif isinstance(plugin_instance, UIComponentPlugin):
            self.ui_components.pop(plugin_name, None)
        elif isinstance(plugin_instance, APIEndpointPlugin):
            self.api_endpoints.pop(plugin_name, None)
        elif isinstance(plugin_instance, IntegrationPlugin):
            self.integrations.pop(plugin_name, None)
