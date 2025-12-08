"""Example audio processor plugin for Talk2Me UI.

This plugin demonstrates how to create custom audio processing plugins
that can modify audio data in real-time.
"""

import logging
from typing import Any, Dict, List
from pydub import AudioSegment

from src.talk2me_ui.plugins.interfaces import (
    AudioProcessorPlugin,
    PluginMetadata,
    PluginLoadContext,
)

logger = logging.getLogger(__name__)


class ExampleAudioProcessor(AudioProcessorPlugin):
    """Example audio processor that applies gain and normalization."""

    def __init__(self):
        self.config = {}
        self.initialized = False

    @property
    def metadata(self) -> PluginMetadata:
        """Return plugin metadata."""
        return PluginMetadata(
            name="example_audio_processor",
            version="1.0.0",
            description="Example audio processor plugin demonstrating the plugin system",
            author="Talk2Me Team",
            plugin_type="audio_processor",
            dependencies=[],
            config_schema={
                "type": "object",
                "properties": {
                    "enabled": {
                        "type": "boolean",
                        "default": True,
                        "description": "Whether the plugin is enabled"
                    },
                    "gain_db": {
                        "type": "number",
                        "default": 0.0,
                        "minimum": -20.0,
                        "maximum": 20.0,
                        "description": "Gain adjustment in decibels"
                    },
                    "normalize": {
                        "type": "boolean",
                        "default": false,
                        "description": "Whether to normalize audio levels"
                    }
                },
                "required": ["enabled"]
            },
            homepage="https://github.com/talk2me/plugins",
            license="MIT",
            tags=["audio", "processing", "example"]
        )

    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the plugin with configuration."""
        logger.info("Initializing Example Audio Processor plugin")

        self.config = config
        self.enabled = config.get("enabled", True)
        self.gain_db = config.get("gain_db", 0.0)
        self.normalize = config.get("normalize", False)

        # Validate configuration
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be a boolean")

        if not isinstance(self.gain_db, (int, float)):
            raise ValueError("gain_db must be a number")

        if self.gain_db < -20.0 or self.gain_db > 20.0:
            raise ValueError("gain_db must be between -20.0 and 20.0")

        if not isinstance(self.normalize, bool):
            raise ValueError("normalize must be a boolean")

        self.initialized = True
        logger.info(f"Example Audio Processor initialized with config: {config}")

    async def shutdown(self) -> None:
        """Shutdown the plugin and cleanup resources."""
        logger.info("Shutting down Example Audio Processor plugin")
        self.initialized = False

    def get_config_schema(self) -> Dict[str, Any]:
        """Return JSON schema for plugin configuration."""
        return self.metadata.config_schema

    async def process_audio(
        self,
        audio: AudioSegment,
        config: Dict[str, Any]
    ) -> AudioSegment:
        """Process audio data.

        Args:
            audio: Input audio segment
            config: Processing configuration (overrides instance config)

        Returns:
            Processed audio segment
        """
        if not self.initialized:
            raise RuntimeError("Plugin not initialized")

        # Merge instance config with processing config
        processing_config = self.config.copy()
        processing_config.update(config)

        if not processing_config.get("enabled", True):
            logger.debug("Plugin disabled, returning original audio")
            return audio

        processed_audio = audio

        # Apply gain adjustment
        gain_db = processing_config.get("gain_db", 0.0)
        if gain_db != 0.0:
            logger.debug(f"Applying gain adjustment: {gain_db} dB")
            processed_audio = processed_audio + gain_db

        # Apply normalization if requested
        if processing_config.get("normalize", False):
            logger.debug("Applying audio normalization")
            # Simple normalization to -3 dBFS
            target_dBFS = -3.0
            current_dBFS = processed_audio.dBFS
            if current_dBFS < target_dBFS:
                gain_needed = target_dBFS - current_dBFS
                processed_audio = processed_audio + gain_needed

        logger.debug(f"Audio processing completed. Original: {len(audio)}ms, Processed: {len(processed_audio)}ms")
        return processed_audio

    def get_supported_formats(self) -> List[str]:
        """Return list of supported audio formats."""
        return ["wav", "mp3", "ogg", "flac", "aac"]

    def get_processing_capabilities(self) -> Dict[str, Any]:
        """Return processing capabilities and parameters."""
        return {
            "gain_adjustment": {
                "range_db": [-20.0, 20.0],
                "default": 0.0
            },
            "normalization": {
                "target_dBFS": -3.0,
                "enabled": True
            },
            "supported_formats": self.get_supported_formats(),
            "real_time_processing": True,
            "max_channels": 2
        }
