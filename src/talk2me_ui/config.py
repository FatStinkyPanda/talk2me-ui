"""Configuration management system for Talk2Me UI.

This module provides Pydantic models for configuration settings and functions
to load configuration from YAML files with validation and error handling.
"""

import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, HttpUrl, ValidationError, field_validator

logger = logging.getLogger("talk2me_ui.config")


class BackendConfig(BaseModel):
    """Configuration for Talk2Me backend connection."""

    url: HttpUrl = Field(default="http://localhost:8000", description="Backend API URL")


class AudioConfig(BaseModel):
    """Configuration for audio settings."""

    sample_rate: int = Field(
        default=16000, ge=8000, le=48000, description="Audio sample rate in Hz"
    )
    channels: int = Field(default=1, ge=1, le=2, description="Number of audio channels")

    @field_validator("sample_rate")
    @classmethod
    def validate_sample_rate(cls, v: int) -> int:
        """Validate sample rate is a common audio rate."""
        common_rates = [8000, 16000, 22050, 24000, 44100, 48000]
        if v not in common_rates:
            raise ValueError(f"Sample rate {v} not in common rates: {common_rates}")
        return v


class UIConfig(BaseModel):
    """Configuration for UI server settings."""

    host: str = Field(default="127.0.0.1", description="UI server host")
    port: int = Field(default=8000, ge=1, le=65535, description="UI server port")


class Config(BaseModel):
    """Main configuration model combining all sections."""

    backend: BackendConfig = Field(default_factory=BackendConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    ui: UIConfig = Field(default_factory=UIConfig)


def load_yaml_config(file_path: Path) -> dict[str, Any]:
    """Load configuration from a YAML file.

    Args:
        file_path: Path to the YAML configuration file

    Returns:
        Dictionary containing the configuration data

    Raises:
        FileNotFoundError: If the configuration file does not exist
        yaml.YAMLError: If the YAML file is malformed
    """
    logger.debug("Loading YAML config", extra={"file_path": str(file_path)})
    try:
        with open(file_path, encoding="utf-8") as f:
            config_data = yaml.safe_load(f) or {}
        logger.info(
            "YAML config loaded successfully",
            extra={"file_path": str(file_path), "keys_count": len(config_data)},
        )
        return config_data
    except FileNotFoundError:
        logger.error("Configuration file not found", extra={"file_path": str(file_path)})
        raise FileNotFoundError(f"Configuration file not found: {file_path}") from None
    except yaml.YAMLError as e:
        logger.error(
            "Invalid YAML in configuration file",
            extra={"file_path": str(file_path), "error": str(e)},
        )
        raise yaml.YAMLError(f"Invalid YAML in {file_path}: {e}") from e


def merge_configs(base_config: dict[str, Any], override_config: dict[str, Any]) -> dict[str, Any]:
    """Merge two configuration dictionaries, with override_config taking precedence.

    Args:
        base_config: Base configuration dictionary
        override_config: Override configuration dictionary

    Returns:
        Merged configuration dictionary
    """
    merged = base_config.copy()

    def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                base[key] = deep_merge(base[key], value)
            else:
                base[key] = value
        return base

    return deep_merge(merged, override_config)


def load_config(
    default_config_path: Path | None = None, user_config_path: Path | None = None
) -> Config:
    """Load and validate configuration from YAML files.

    Loads default configuration and optionally merges with user configuration.

    Args:
        default_config_path: Path to default configuration file (default: config/default.yaml)
        user_config_path: Path to user configuration file (default: config/user.yaml)

    Returns:
        Validated Config object

    Raises:
        FileNotFoundError: If default config file is not found
        yaml.YAMLError: If any config file is malformed
        ValidationError: If configuration data fails validation
    """
    if default_config_path is None:
        default_config_path = Path(__file__).parent.parent.parent / "config" / "default.yaml"

    logger.debug(
        "Loading configuration",
        extra={
            "default_config_path": str(default_config_path),
            "user_config_path": str(user_config_path) if user_config_path else None,
        },
    )

    # Load default configuration
    default_config = load_yaml_config(default_config_path)

    # Load user configuration if it exists
    user_config = {}
    if user_config_path is None:
        user_config_path = Path(__file__).parent.parent.parent / "config" / "user.yaml"

    if user_config_path.exists():
        user_config = load_yaml_config(user_config_path)
        logger.info(
            "User configuration loaded and merged", extra={"user_config_keys": len(user_config)}
        )
    else:
        logger.debug("No user configuration file found, using defaults only")

    # Merge configurations
    merged_config = merge_configs(default_config, user_config)

    # Validate and create Config object
    try:
        config = Config(**merged_config)
        logger.info(
            "Configuration loaded and validated successfully",
            extra={
                "backend_url": str(config.backend.url),
                "ui_host": config.ui.host,
                "ui_port": config.ui.port,
                "audio_sample_rate": config.audio.sample_rate,
            },
        )
        return config
    except ValidationError as e:
        logger.error(
            "Configuration validation failed", extra={"validation_errors": str(e)}, exc_info=True
        )
        raise ValueError(f"Configuration validation failed: {e}") from e


# Global configuration instance
_config: Config | None = None


def get_config() -> Config:
    """Get the global configuration instance.

    Loads configuration on first call if not already loaded.

    Returns:
        Global Config instance
    """
    global _config
    if _config is None:
        logger.debug("Loading global configuration instance")
        _config = load_config()
        logger.info("Global configuration instance loaded")
    else:
        logger.debug("Returning cached global configuration instance")
    return _config


def reload_config(
    default_config_path: Path | None = None, user_config_path: Path | None = None
) -> Config:
    """Reload configuration from files.

    Args:
        default_config_path: Path to default configuration file
        user_config_path: Path to user configuration file

    Returns:
        Reloaded Config object
    """
    global _config
    _config = load_config(default_config_path, user_config_path)
    return _config
