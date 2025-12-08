"""Plugin marketplace for browsing and installing plugins."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import aiohttp
import hashlib
import tempfile
import zipfile
import shutil

logger = logging.getLogger(__name__)


class PluginMarketplace:
    """Manages plugin marketplace operations including browsing and installation."""

    def __init__(self, marketplace_url: str, plugins_dir: Path, cache_dir: Optional[Path] = None):
        self.marketplace_url = marketplace_url.rstrip('/')
        self.plugins_dir = plugins_dir
        self.cache_dir = cache_dir or (plugins_dir / ".cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # HTTP client session
        self.session: Optional[aiohttp.ClientSession] = None

    async def initialize(self) -> None:
        """Initialize the marketplace client."""
        self.session = aiohttp.ClientSession()

    async def shutdown(self) -> None:
        """Shutdown the marketplace client."""
        if self.session:
            await self.session.close()
            self.session = None

    async def list_available_plugins(
        self,
        category: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """List available plugins from the marketplace.

        Args:
            category: Optional category filter
            search: Optional search query
            limit: Maximum number of results
            offset: Pagination offset

        Returns:
            Dict containing plugins list and metadata
        """
        if not self.session:
            raise RuntimeError("Marketplace not initialized")

        params = {
            'limit': limit,
            'offset': offset,
        }

        if category:
            params['category'] = category
        if search:
            params['search'] = search

        try:
            async with self.session.get(f"{self.marketplace_url}/api/plugins", params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Failed to fetch plugins: HTTP {response.status}")
                    return {'plugins': [], 'total': 0}

        except Exception as e:
            logger.error(f"Error fetching plugins from marketplace: {e}")
            return {'plugins': [], 'total': 0}

    async def get_plugin_details(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific plugin.

        Args:
            plugin_id: Unique plugin identifier

        Returns:
            Plugin details or None if not found
        """
        if not self.session:
            raise RuntimeError("Marketplace not initialized")

        try:
            async with self.session.get(f"{self.marketplace_url}/api/plugins/{plugin_id}") as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 404:
                    return None
                else:
                    logger.error(f"Failed to fetch plugin details: HTTP {response.status}")
                    return None

        except Exception as e:
            logger.error(f"Error fetching plugin details: {e}")
            return None

    async def install_plugin(self, plugin_id: str, version: Optional[str] = None) -> bool:
        """Install a plugin from the marketplace.

        Args:
            plugin_id: Unique plugin identifier
            version: Optional specific version to install

        Returns:
            True if installation successful
        """
        if not self.session:
            raise RuntimeError("Marketplace not initialized")

        try:
            # Get plugin details
            details = await self.get_plugin_details(plugin_id)
            if not details:
                logger.error(f"Plugin not found: {plugin_id}")
                return False

            # Use specified version or latest
            target_version = version or details.get('latest_version', {}).get('version')
            if not target_version:
                logger.error(f"No version available for plugin: {plugin_id}")
                return False

            # Find download URL
            download_url = None
            for version_info in details.get('versions', []):
                if version_info['version'] == target_version:
                    download_url = version_info.get('download_url')
                    break

            if not download_url:
                logger.error(f"No download URL found for plugin {plugin_id} version {target_version}")
                return False

            # Download and install
            return await self._download_and_install_plugin(download_url, plugin_id, target_version)

        except Exception as e:
            logger.error(f"Error installing plugin {plugin_id}: {e}", exc_info=True)
            return False

    async def uninstall_plugin(self, plugin_name: str) -> bool:
        """Uninstall a plugin.

        Args:
            plugin_name: Name of the plugin to uninstall

        Returns:
            True if uninstallation successful
        """
        try:
            plugin_path = self.plugins_dir / plugin_name
            if not plugin_path.exists():
                logger.warning(f"Plugin not installed: {plugin_name}")
                return False

            # Remove plugin directory
            shutil.rmtree(plugin_path)
            logger.info(f"Successfully uninstalled plugin: {plugin_name}")
            return True

        except Exception as e:
            logger.error(f"Error uninstalling plugin {plugin_name}: {e}")
            return False

    async def update_plugin(self, plugin_name: str) -> bool:
        """Update a plugin to the latest version.

        Args:
            plugin_name: Name of the plugin to update

        Returns:
            True if update successful
        """
        try:
            # Get current plugin metadata
            plugin_path = self.plugins_dir / plugin_name
            metadata_file = plugin_path / "plugin.json"

            if not metadata_file.exists():
                logger.error(f"Plugin metadata not found: {plugin_name}")
                return False

            with open(metadata_file, 'r') as f:
                current_metadata = json.load(f)

            plugin_id = current_metadata.get('marketplace_id')
            if not plugin_id:
                logger.error(f"No marketplace ID found for plugin: {plugin_name}")
                return False

            # Get latest version from marketplace
            details = await self.get_plugin_details(plugin_id)
            if not details:
                logger.error(f"Plugin not found in marketplace: {plugin_id}")
                return False

            latest_version = details.get('latest_version', {}).get('version')
            current_version = current_metadata.get('version')

            if latest_version == current_version:
                logger.info(f"Plugin {plugin_name} is already up to date")
                return True

            # Install new version
            if await self.install_plugin(plugin_id, latest_version):
                # Remove old version
                shutil.rmtree(plugin_path)
                logger.info(f"Successfully updated plugin {plugin_name} to version {latest_version}")
                return True
            else:
                return False

        except Exception as e:
            logger.error(f"Error updating plugin {plugin_name}: {e}", exc_info=True)
            return False

    async def get_installed_plugins(self) -> List[Dict[str, Any]]:
        """Get list of installed plugins with their status.

        Returns:
            List of installed plugin information
        """
        installed_plugins = []

        for plugin_dir in self.plugins_dir.iterdir():
            if plugin_dir.is_dir() and not plugin_dir.name.startswith('.'):
                metadata_file = plugin_dir / "plugin.json"
                if metadata_file.exists():
                    try:
                        with open(metadata_file, 'r') as f:
                            metadata = json.load(f)

                        installed_plugins.append({
                            'name': plugin_dir.name,
                            'version': metadata.get('version'),
                            'description': metadata.get('description'),
                            'author': metadata.get('author'),
                            'type': metadata.get('type'),
                            'path': str(plugin_dir),
                        })

                    except Exception as e:
                        logger.warning(f"Failed to read metadata for plugin {plugin_dir.name}: {e}")

        return installed_plugins

    async def check_for_updates(self) -> List[Dict[str, Any]]:
        """Check for available updates for installed plugins.

        Returns:
            List of plugins with available updates
        """
        updates_available = []
        installed_plugins = await self.get_installed_plugins()

        for plugin in installed_plugins:
            marketplace_id = plugin.get('marketplace_id')
            if marketplace_id:
                details = await self.get_plugin_details(marketplace_id)
                if details:
                    latest_version = details.get('latest_version', {}).get('version')
                    if latest_version and latest_version != plugin['version']:
                        updates_available.append({
                            'name': plugin['name'],
                            'current_version': plugin['version'],
                            'latest_version': latest_version,
                            'description': details.get('description'),
                        })

        return updates_available

    async def _download_and_install_plugin(self, download_url: str, plugin_id: str, version: str) -> bool:
        """Download and install a plugin from URL.

        Args:
            download_url: URL to download plugin archive
            plugin_id: Plugin identifier
            version: Plugin version

        Returns:
            True if installation successful
        """
        try:
            # Download to temporary file
            async with self.session.get(download_url) as response:
                if response.status != 200:
                    logger.error(f"Failed to download plugin: HTTP {response.status}")
                    return False

                with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_file:
                    tmp_path = Path(tmp_file.name)
                    tmp_file.write(await response.read())

            # Extract to plugins directory
            plugin_dir = self.plugins_dir / plugin_id
            if plugin_dir.exists():
                shutil.rmtree(plugin_dir)

            plugin_dir.mkdir(parents=True)

            with zipfile.ZipFile(tmp_path, 'r') as zip_ref:
                zip_ref.extractall(plugin_dir)

            # Cleanup
            tmp_path.unlink()

            # Verify installation
            metadata_file = plugin_dir / "plugin.json"
            if not metadata_file.exists():
                logger.error(f"Plugin archive missing metadata file: {plugin_id}")
                shutil.rmtree(plugin_dir)
                return False

            logger.info(f"Successfully installed plugin: {plugin_id} v{version}")
            return True

        except Exception as e:
            logger.error(f"Error during plugin installation: {e}", exc_info=True)
            return False
