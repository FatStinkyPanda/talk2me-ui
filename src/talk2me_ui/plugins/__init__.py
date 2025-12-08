"""Plugin system for Talk2Me UI extensibility.

This module provides a comprehensive plugin architecture that allows third-party
developers to extend the application with custom audio processors, UI components,
API endpoints, and integrations.
"""

from .discovery import PluginDiscovery
from .interfaces import (
    APIEndpointPlugin,
    AudioProcessorPlugin,
    IntegrationPlugin,
    PluginInterface,
    UIComponentPlugin,
)
from .lifecycle import PluginLifecycle
from .marketplace import PluginMarketplace
from .plugin_manager import PluginManager

__all__ = [
    "PluginManager",
    "PluginInterface",
    "AudioProcessorPlugin",
    "UIComponentPlugin",
    "APIEndpointPlugin",
    "IntegrationPlugin",
    "PluginDiscovery",
    "PluginLifecycle",
    "PluginMarketplace",
]
