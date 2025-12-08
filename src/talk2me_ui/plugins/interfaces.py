"""Plugin interfaces for different plugin types.

This module defines the base interfaces that plugins must implement
to integrate with the Talk2Me UI plugin system.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Protocol, Union
from pathlib import Path
import asyncio
from fastapi import Request, Response
from pydub import AudioSegment


class PluginMetadata:
    """Metadata for a plugin."""

    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        author: str,
        plugin_type: str,
        dependencies: Optional[List[str]] = None,
        config_schema: Optional[Dict[str, Any]] = None,
        homepage: Optional[str] = None,
        license: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ):
        self.name = name
        self.version = version
        self.description = description
        self.author = author
        self.plugin_type = plugin_type
        self.dependencies = dependencies or []
        self.config_schema = config_schema or {}
        self.homepage = homepage
        self.license = license
        self.tags = tags or []


class PluginInterface(ABC):
    """Base interface that all plugins must implement."""

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Return plugin metadata."""
        pass

    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the plugin with configuration."""
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown the plugin and cleanup resources."""
        pass

    @abstractmethod
    def get_config_schema(self) -> Dict[str, Any]:
        """Return JSON schema for plugin configuration."""
        pass


class AudioProcessorPlugin(PluginInterface):
    """Interface for audio processing plugins."""

    @abstractmethod
    async def process_audio(
        self,
        audio: AudioSegment,
        config: Dict[str, Any]
    ) -> AudioSegment:
        """Process audio data.

        Args:
            audio: Input audio segment
            config: Processing configuration

        Returns:
            Processed audio segment
        """
        pass

    @abstractmethod
    def get_supported_formats(self) -> List[str]:
        """Return list of supported audio formats."""
        pass

    @abstractmethod
    def get_processing_capabilities(self) -> Dict[str, Any]:
        """Return processing capabilities and parameters."""
        pass


class UIComponentPlugin(PluginInterface):
    """Interface for UI component plugins."""

    @abstractmethod
    def get_component_type(self) -> str:
        """Return the type of UI component (e.g., 'button', 'panel', 'widget')."""
        pass

    @abstractmethod
    def render_component(self, config: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Render the component as HTML.

        Args:
            config: Component configuration
            context: Rendering context

        Returns:
            HTML string for the component
        """
        pass

    @abstractmethod
    def get_javascript_assets(self) -> List[str]:
        """Return list of JavaScript asset paths."""
        pass

    @abstractmethod
    def get_css_assets(self) -> List[str]:
        """Return list of CSS asset paths."""
        pass


class APIEndpointPlugin(PluginInterface):
    """Interface for API endpoint plugins."""

    @abstractmethod
    def get_routes(self) -> List[Dict[str, Any]]:
        """Return list of route definitions.

        Each route should be a dict with:
        - path: str - API path
        - methods: List[str] - HTTP methods
        - handler: callable - Route handler function
        - name: str - Route name
        - tags: List[str] - OpenAPI tags
        """
        pass

    @abstractmethod
    def get_openapi_extensions(self) -> Dict[str, Any]:
        """Return OpenAPI extensions for the plugin."""
        pass


class IntegrationPlugin(PluginInterface):
    """Interface for integration plugins (external services)."""

    @abstractmethod
    async def connect(self, credentials: Dict[str, Any]) -> bool:
        """Establish connection to external service.

        Args:
            credentials: Authentication credentials

        Returns:
            True if connection successful
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from external service."""
        pass

    @abstractmethod
    def get_integration_type(self) -> str:
        """Return integration type (e.g., 'slack', 'discord', 'webhook')."""
        pass

    @abstractmethod
    async def send_message(self, message: Dict[str, Any]) -> bool:
        """Send message through integration.

        Args:
            message: Message data

        Returns:
            True if sent successfully
        """
        pass

    @abstractmethod
    async def receive_messages(self) -> List[Dict[str, Any]]:
        """Receive messages from integration.

        Returns:
            List of received messages
        """
        pass


class PluginContext:
    """Context provided to plugins during execution."""

    def __init__(
        self,
        app_config: Dict[str, Any],
        database_manager: Any,
        api_client: Any,
        user_manager: Any,
        cache_manager: Any,
    ):
        self.app_config = app_config
        self.database_manager = database_manager
        self.api_client = api_client
        self.user_manager = user_manager
        self.cache_manager = cache_manager


class PluginLoadContext:
    """Context provided during plugin loading."""

    def __init__(
        self,
        plugin_path: Path,
        plugin_config: Dict[str, Any],
        context: PluginContext,
    ):
        self.plugin_path = plugin_path
        self.plugin_config = plugin_config
        self.context = context
