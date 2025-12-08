"""Plugin system for Talk2Me UI extensibility.

This module provides a comprehensive plugin architecture that allows third-party
developers to extend the application with custom audio processors, UI components,
API endpoints, and integrations.
"""

from .plugin_manager import PluginManager
from .interfaces import (
    PluginInterface,
    AudioProcessorPlugin,
    UIComponentPlugin,
    APIEndpointPlugin,
    IntegrationPlugin,
)
from .discovery import PluginDiscovery
from .lifecycle import PluginLifecycle
from .marketplace import PluginMarketplace

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
