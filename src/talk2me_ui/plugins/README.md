# Talk2Me UI Plugin System

The Talk2Me UI plugin system provides a comprehensive architecture for extending the application with custom functionality. This system allows third-party developers to create plugins that can add audio processors, UI components, API endpoints, and integrations without modifying the core application code.

## Overview

The plugin system consists of several key components:

- **Plugin Interfaces**: Define the contracts that plugins must implement
- **Plugin Manager**: Central coordinator for plugin loading and management
- **Plugin Discovery**: Automatic detection of available plugins
- **Plugin Lifecycle**: Management of plugin activation and deactivation
- **Plugin Marketplace**: Interface for browsing and installing plugins

## Plugin Types

### Audio Processor Plugins

Audio processor plugins can modify audio data in real-time. They implement the `AudioProcessorPlugin` interface and can perform operations like:

- Volume normalization
- Noise reduction
- Audio effects (reverb, echo, etc.)
- Format conversion
- Audio analysis

### UI Component Plugins

UI component plugins add new user interface elements to the application. They implement the `UIComponentPlugin` interface and can provide:

- Custom dashboard widgets
- New page templates
- Interactive components
- Custom styling

### API Endpoint Plugins

API endpoint plugins extend the REST API with new endpoints. They implement the `APIEndpointPlugin` interface and can add:

- Custom data endpoints
- Integration APIs
- Administrative functions
- Third-party service proxies

### Integration Plugins

Integration plugins connect the application to external services. They implement the `IntegrationPlugin` interface and can provide:

- Slack/Discord integrations
- Webhook support
- External API connections
- Data synchronization

## Plugin Structure

Each plugin is a directory containing:

```
plugin_name/
├── plugin.json    # Plugin metadata and configuration schema
├── plugin.py      # Main plugin implementation
├── static/        # Static assets (optional)
├── templates/     # Jinja2 templates (optional)
└── README.md      # Plugin documentation (optional)
```

### plugin.json

The `plugin.json` file contains plugin metadata:

```json
{
  "name": "my_plugin",
  "version": "1.0.0",
  "description": "Description of what the plugin does",
  "author": "Your Name",
  "type": "audio_processor",
  "dependencies": ["other_plugin"],
  "config_schema": {
    "type": "object",
    "properties": {
      "enabled": {
        "type": "boolean",
        "default": true
      }
    }
  },
  "homepage": "https://github.com/your/plugin",
  "license": "MIT",
  "tags": ["audio", "processing"]
}
```

### plugin.py

The main plugin implementation must contain a class that inherits from the appropriate plugin interface:

```python
from src.talk2me_ui.plugins.interfaces import AudioProcessorPlugin, PluginMetadata

class MyAudioProcessor(AudioProcessorPlugin):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="my_audio_processor",
            version="1.0.0",
            description="My custom audio processor",
            author="Your Name",
            plugin_type="audio_processor",
        )

    async def initialize(self, config: Dict[str, Any]) -> None:
        # Initialize your plugin
        pass

    async def shutdown(self) -> None:
        # Cleanup resources
        pass

    async def process_audio(self, audio: AudioSegment, config: Dict[str, Any]) -> AudioSegment:
        # Process audio and return result
        return audio
```

## Plugin Development

### Setting Up Development Environment

1. Create a new directory in `data/plugins/` for your plugin
2. Implement the required interface methods
3. Test your plugin using the development server
4. Package and distribute your plugin

### Best Practices

- **Error Handling**: Always handle errors gracefully and log appropriately
- **Configuration**: Use the config schema to validate user input
- **Dependencies**: Declare all dependencies in `plugin.json`
- **Documentation**: Provide clear documentation for configuration options
- **Testing**: Include comprehensive tests for your plugin
- **Security**: Validate all inputs and avoid security vulnerabilities

### Configuration Schema

Plugins use JSON Schema for configuration validation:

```json
{
  "type": "object",
  "properties": {
    "setting_name": {
      "type": "string",
      "description": "Description of the setting",
      "default": "default_value"
    }
  },
  "required": ["setting_name"]
}
```

## Plugin Management

### Installing Plugins

Plugins can be installed from the marketplace or manually:

```bash
# From marketplace
curl -X POST /api/plugins/marketplace/install/plugin_name

# Manual installation
cp -r my_plugin data/plugins/
```

### Activating Plugins

```bash
curl -X POST /api/plugins/my_plugin/activate
```

### Configuring Plugins

Plugin configuration is managed through the web interface or API:

```bash
curl -X PUT /api/plugins/my_plugin/config \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "gain_db": 3.0}'
```

## API Reference

### Plugin Management Endpoints

- `GET /api/plugins` - List installed plugins
- `GET /api/plugins/{name}` - Get plugin information
- `POST /api/plugins/{name}/activate` - Activate plugin
- `POST /api/plugins/{name}/deactivate` - Deactivate plugin
- `POST /api/plugins/marketplace/install/{id}` - Install from marketplace
- `POST /api/plugins/{name}/uninstall` - Uninstall plugin
- `POST /api/plugins/{name}/update` - Update plugin

### Marketplace Endpoints

- `GET /api/plugins/marketplace` - Browse available plugins
- `GET /api/plugins/updates` - Check for updates

## Example Plugin

See `data/plugins/example_audio_processor/` for a complete working example of an audio processor plugin.

## Security Considerations

- Plugins run with the same permissions as the main application
- Always validate plugin code before installation
- Use sandboxing for untrusted plugins in production
- Implement proper access controls for plugin APIs

## Contributing

To contribute a plugin to the official marketplace:

1. Ensure your plugin follows the plugin interface contracts
2. Include comprehensive documentation
3. Provide test coverage
4. Submit a pull request to the plugins repository

## License

Plugin system code is licensed under MIT. Individual plugins may have their own licenses as specified in their `plugin.json` files.
