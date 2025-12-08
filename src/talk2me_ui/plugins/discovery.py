"""Plugin discovery mechanism for finding and validating plugins."""

import asyncio
import json
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class PluginDiscovery:
    """Handles discovery and validation of plugins in the plugins directory."""

    def __init__(self, plugins_dir: Path):
        self.plugins_dir = plugins_dir
        self.plugins_dir.mkdir(parents=True, exist_ok=True)

    async def discover_plugins(self) -> List[str]:
        """Discover all available plugins in the plugins directory.

        Returns:
            List of plugin names that are valid and available
        """
        if not self.plugins_dir.exists():
            logger.warning(f"Plugins directory does not exist: {self.plugins_dir}")
            return []

        plugin_names = []

        for item in self.plugins_dir.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                if await self._is_valid_plugin(item):
                    plugin_names.append(item.name)
                else:
                    logger.warning(f"Invalid plugin directory: {item}")

        logger.info(f"Discovered {len(plugin_names)} valid plugins")
        return plugin_names

    async def validate_plugin(self, plugin_name: str) -> bool:
        """Validate a specific plugin.

        Args:
            plugin_name: Name of the plugin to validate

        Returns:
            True if plugin is valid
        """
        plugin_path = self.plugins_dir / plugin_name
        return await self._is_valid_plugin(plugin_path)

    async def get_plugin_info(self, plugin_name: str) -> Optional[dict]:
        """Get basic information about a plugin without loading it.

        Args:
            plugin_name: Name of the plugin

        Returns:
            Plugin information dict or None if not found/invalid
        """
        plugin_path = self.plugins_dir / plugin_name
        if not plugin_path.exists() or not plugin_path.is_dir():
            return None

        metadata_file = plugin_path / "plugin.json"
        if not metadata_file.exists():
            return None

        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)

            # Basic validation
            required_fields = ["name", "version", "description", "author", "type"]
            if not all(field in metadata for field in required_fields):
                logger.error(f"Plugin {plugin_name} missing required metadata fields")
                return None

            return {
                "name": metadata["name"],
                "version": metadata["version"],
                "description": metadata["description"],
                "author": metadata["author"],
                "type": metadata["type"],
                "path": str(plugin_path),
                "dependencies": metadata.get("dependencies", []),
                "tags": metadata.get("tags", []),
                "homepage": metadata.get("homepage"),
                "license": metadata.get("license"),
            }

        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Failed to read plugin metadata for {plugin_name}: {e}")
            return None

    async def list_plugin_files(self, plugin_name: str) -> List[str]:
        """List all files in a plugin directory.

        Args:
            plugin_name: Name of the plugin

        Returns:
            List of file paths relative to plugin directory
        """
        plugin_path = self.plugins_dir / plugin_name
        if not plugin_path.exists():
            return []

        files = []
        for file_path in plugin_path.rglob("*"):
            if file_path.is_file():
                files.append(str(file_path.relative_to(plugin_path)))

        return files

    async def _is_valid_plugin(self, plugin_path: Path) -> bool:
        """Check if a directory contains a valid plugin.

        Args:
            plugin_path: Path to the plugin directory

        Returns:
            True if directory contains a valid plugin
        """
        if not plugin_path.is_dir():
            return False

        # Check for plugin.json metadata file
        metadata_file = plugin_path / "plugin.json"
        if not metadata_file.exists():
            return False

        # Validate metadata file
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)

            # Check required fields
            required_fields = ["name", "version", "description", "author", "type"]
            if not all(field in metadata for field in required_fields):
                logger.error(f"Plugin {plugin_path.name} missing required metadata fields")
                return False

            # Validate plugin type
            valid_types = ["audio_processor", "ui_component", "api_endpoint", "integration"]
            if metadata["type"] not in valid_types:
                logger.error(f"Plugin {plugin_path.name} has invalid type: {metadata['type']}")
                return False

            # Check for main plugin file
            has_plugin_file = False
            for file_path in plugin_path.glob("*.py"):
                if file_path.name != "__init__.py":
                    has_plugin_file = True
                    break

            if not has_plugin_file:
                logger.error(f"Plugin {plugin_path.name} has no main plugin file")
                return False

            return True

        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Invalid plugin metadata in {plugin_path}: {e}")
            return False
