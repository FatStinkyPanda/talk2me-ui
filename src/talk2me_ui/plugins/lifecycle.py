"""Plugin lifecycle management for activation and deactivation."""

import logging
from typing import Any, Dict
from .interfaces import PluginInterface, PluginLoadContext

logger = logging.getLogger(__name__)


class PluginLifecycle:
    """Manages the lifecycle of plugins including activation and deactivation."""

    def __init__(self):
        self.active_plugins: Dict[str, PluginInterface] = {}
        self.plugin_states: Dict[str, str] = {}  # 'initializing', 'active', 'deactivating', 'inactive'

    async def activate_plugin(
        self,
        plugin_name: str,
        plugin_instance: PluginInterface,
        context: PluginLoadContext
    ) -> bool:
        """Activate a plugin instance.

        Args:
            plugin_name: Name of the plugin
            plugin_instance: Plugin instance to activate
            context: Loading context with configuration

        Returns:
            True if activation successful
        """
        try:
            logger.info(f"Activating plugin: {plugin_name}")
            self.plugin_states[plugin_name] = 'initializing'

            # Initialize the plugin
            await plugin_instance.initialize(context.plugin_config)

            # Mark as active
            self.active_plugins[plugin_name] = plugin_instance
            self.plugin_states[plugin_name] = 'active'

            logger.info(f"Successfully activated plugin: {plugin_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to activate plugin {plugin_name}: {e}", exc_info=True)
            self.plugin_states[plugin_name] = 'inactive'
            return False

    async def deactivate_plugin(self, plugin_name: str, plugin_instance: PluginInterface) -> bool:
        """Deactivate a plugin instance.

        Args:
            plugin_name: Name of the plugin
            plugin_instance: Plugin instance to deactivate

        Returns:
            True if deactivation successful
        """
        try:
            logger.info(f"Deactivating plugin: {plugin_name}")
            self.plugin_states[plugin_name] = 'deactivating'

            # Shutdown the plugin
            await plugin_instance.shutdown()

            # Remove from active plugins
            if plugin_name in self.active_plugins:
                del self.active_plugins[plugin_name]

            self.plugin_states[plugin_name] = 'inactive'

            logger.info(f"Successfully deactivated plugin: {plugin_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to deactivate plugin {plugin_name}: {e}", exc_info=True)
            # Still mark as inactive even if shutdown failed
            self.plugin_states[plugin_name] = 'inactive'
            return False

    def is_plugin_active(self, plugin_name: str) -> bool:
        """Check if a plugin is currently active.

        Args:
            plugin_name: Name of the plugin

        Returns:
            True if plugin is active
        """
        return (plugin_name in self.active_plugins and
                self.plugin_states.get(plugin_name) == 'active')

    def get_plugin_state(self, plugin_name: str) -> str:
        """Get the current state of a plugin.

        Args:
            plugin_name: Name of the plugin

        Returns:
            Plugin state string
        """
        return self.plugin_states.get(plugin_name, 'unknown')

    def list_active_plugins(self) -> list[str]:
        """List names of all active plugins.

        Returns:
            List of active plugin names
        """
        return [name for name, state in self.plugin_states.items() if state == 'active']

    async def reload_plugin(
        self,
        plugin_name: str,
        plugin_instance: PluginInterface,
        new_config: Dict[str, Any]
    ) -> bool:
        """Reload a plugin with new configuration.

        Args:
            plugin_name: Name of the plugin
            plugin_instance: Current plugin instance
            new_config: New configuration to apply

        Returns:
            True if reload successful
        """
        try:
            logger.info(f"Reloading plugin: {plugin_name}")

            # Shutdown current instance
            await plugin_instance.shutdown()

            # Reinitialize with new config
            await plugin_instance.initialize(new_config)

            logger.info(f"Successfully reloaded plugin: {plugin_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to reload plugin {plugin_name}: {e}", exc_info=True)
            return False

    async def validate_plugin_config(
        self,
        plugin_instance: PluginInterface,
        config: Dict[str, Any]
    ) -> bool:
        """Validate plugin configuration against schema.

        Args:
            plugin_instance: Plugin instance
            config: Configuration to validate

        Returns:
            True if configuration is valid
        """
        try:
            schema = plugin_instance.get_config_schema()

            # Basic validation - in production you'd use a proper JSON schema validator
            if schema:
                # Check required fields
                required = schema.get('required', [])
                for field in required:
                    if field not in config:
                        logger.error(f"Missing required config field: {field}")
                        return False

                # Check field types
                properties = schema.get('properties', {})
                for field, field_schema in properties.items():
                    if field in config:
                        expected_type = field_schema.get('type')
                        if expected_type:
                            actual_value = config[field]
                            if not self._validate_type(actual_value, expected_type):
                                logger.error(f"Invalid type for field {field}: expected {expected_type}")
                                return False

            return True

        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            return False

    def _validate_type(self, value: Any, expected_type: str) -> bool:
        """Validate a value against an expected type.

        Args:
            value: Value to validate
            expected_type: Expected JSON schema type

        Returns:
            True if type matches
        """
        type_map = {
            'string': str,
            'number': (int, float),
            'integer': int,
            'boolean': bool,
            'array': list,
            'object': dict,
        }

        expected_python_type = type_map.get(expected_type)
        if expected_python_type:
            if isinstance(expected_python_type, tuple):
                return isinstance(value, expected_python_type)
            else:
                return isinstance(value, expected_python_type)

        return True  # Unknown type, assume valid
