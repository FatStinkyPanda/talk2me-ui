"""Unit tests for configuration management module."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from pydantic import ValidationError

from talk2me_ui.config import (
    AudioConfig,
    BackendConfig,
    Config,
    UIConfig,
    get_config,
    load_config,
    load_yaml_config,
    merge_configs,
    reload_config,
)


class TestBackendConfig:
    """Test BackendConfig model."""

    def test_valid_url(self):
        """Test valid backend URL."""
        config = BackendConfig(url="https://api.example.com")
        assert str(config.url) == "https://api.example.com/"

    def test_default_url(self):
        """Test default backend URL."""
        config = BackendConfig()
        assert str(config.url) == "http://localhost:8000"


class TestAudioConfig:
    """Test AudioConfig model."""

    def test_valid_sample_rates(self):
        """Test valid sample rates."""
        for rate in [8000, 16000, 22050, 24000, 44100, 48000]:
            config = AudioConfig(sample_rate=rate)
            assert config.sample_rate == rate

    def test_invalid_sample_rate(self):
        """Test invalid sample rate raises error."""
        with pytest.raises(ValueError, match="Sample rate .* not in common rates"):
            AudioConfig(sample_rate=12345)

    def test_valid_channels(self):
        """Test valid channel counts."""
        config = AudioConfig(channels=1)
        assert config.channels == 1

        config = AudioConfig(channels=2)
        assert config.channels == 2

    def test_invalid_channels(self):
        """Test invalid channel count."""
        with pytest.raises(ValidationError):
            AudioConfig(channels=3)

    def test_defaults(self):
        """Test default values."""
        config = AudioConfig()
        assert config.sample_rate == 16000
        assert config.channels == 1


class TestUIConfig:
    """Test UIConfig model."""

    def test_valid_config(self):
        """Test valid UI configuration."""
        config = UIConfig(host="127.0.0.1", port=3000)
        assert config.host == "127.0.0.1"
        assert config.port == 3000

    def test_invalid_port(self):
        """Test invalid port number."""
        with pytest.raises(ValidationError):
            UIConfig(port=70000)

    def test_defaults(self):
        """Test default values."""
        config = UIConfig()
        assert config.host == "127.0.0.1"
        assert config.port == 8000


class TestConfig:
    """Test main Config model."""

    def test_valid_config(self):
        """Test valid complete configuration."""
        config = Config(
            backend=BackendConfig(url="https://api.test.com"),
            audio=AudioConfig(sample_rate=44100, channels=2),
            ui=UIConfig(host="localhost", port=3000),
        )
        assert str(config.backend.url) == "https://api.test.com/"
        assert config.audio.sample_rate == 44100
        assert config.audio.channels == 2
        assert config.ui.host == "localhost"
        assert config.ui.port == 3000

    def test_default_config(self):
        """Test configuration with all defaults."""
        config = Config()
        assert str(config.backend.url) == "http://localhost:8000"
        assert config.audio.sample_rate == 16000
        assert config.audio.channels == 1
        assert config.ui.host == "127.0.0.1"
        assert config.ui.port == 8000


class TestLoadYamlConfig:
    """Test load_yaml_config function."""

    def test_load_valid_yaml(self):
        """Test loading valid YAML file."""
        yaml_content = """
        backend:
          url: https://api.test.com
        audio:
          sample_rate: 44100
        ui:
          port: 3000
        """

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                result = load_yaml_config(Path(f.name))
                assert result["backend"]["url"] == "https://api.test.com"
                assert result["audio"]["sample_rate"] == 44100
                assert result["ui"]["port"] == 3000
            finally:
                Path(f.name).unlink()

    def test_load_empty_file(self):
        """Test loading empty YAML file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")
            f.flush()

            try:
                result = load_yaml_config(Path(f.name))
                assert result == {}
            finally:
                Path(f.name).unlink()

    def test_file_not_found(self):
        """Test file not found error."""
        with pytest.raises(FileNotFoundError, match="Configuration file not found"):
            load_yaml_config(Path("/nonexistent/file.yaml"))

    def test_invalid_yaml(self):
        """Test invalid YAML content."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content: [\n")
            f.flush()

            try:
                with pytest.raises(yaml.YAMLError):
                    load_yaml_config(Path(f.name))
            finally:
                Path(f.name).unlink()


class TestMergeConfigs:
    """Test merge_configs function."""

    def test_merge_basic(self):
        """Test basic config merging."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = merge_configs(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_merge_nested(self):
        """Test nested config merging."""
        base = {"backend": {"url": "http://old.com", "timeout": 30}}
        override = {"backend": {"url": "http://new.com"}}
        result = merge_configs(base, override)
        assert result == {"backend": {"url": "http://new.com", "timeout": 30}}

    def test_merge_empty_override(self):
        """Test merging with empty override."""
        base = {"a": 1, "b": 2}
        result = merge_configs(base, {})
        assert result == {"a": 1, "b": 2}

    def test_merge_empty_base(self):
        """Test merging with empty base."""
        override = {"a": 1, "b": 2}
        result = merge_configs({}, override)
        assert result == {"a": 1, "b": 2}


class TestLoadConfig:
    """Test load_config function."""

    @patch("talk2me_ui.config.Path")
    def test_load_default_only(self, mock_path):
        """Test loading with default config only."""
        # Mock the default config path
        mock_path.return_value.parent.parent.parent = Path("/fake")

        with patch("talk2me_ui.config.load_yaml_config") as mock_load:
            mock_load.return_value = {
                "backend": {"url": "http://test.com"},
                "audio": {"sample_rate": 16000},
                "ui": {"host": "127.0.0.1", "port": 8000},
            }

            config = load_config()

            assert str(config.backend.url) == "http://test.com/"
            assert config.audio.sample_rate == 16000
            assert config.ui.host == "127.0.0.1"
            assert config.ui.port == 8000

    @patch("talk2me_ui.config.Path")
    def test_load_with_user_config(self, mock_path):
        """Test loading with both default and user config."""
        mock_path.return_value.parent.parent.parent = Path("/fake")

        with (
            patch("talk2me_ui.config.load_yaml_config") as mock_load,
            patch("pathlib.Path.exists") as mock_exists,
        ):
            mock_load.side_effect = [
                {
                    "backend": {"url": "http://default.com"},
                    "audio": {"sample_rate": 16000},
                },  # default
                {"backend": {"url": "http://user.com"}, "ui": {"port": 3000}},  # user
            ]
            mock_exists.return_value = True

            config = load_config()

            assert str(config.backend.url) == "http://user.com/"  # user overrides
            assert config.audio.sample_rate == 16000  # from default
            assert config.ui.port == 3000  # from user

    def test_invalid_config_data(self):
        """Test loading invalid configuration data."""
        with patch("talk2me_ui.config.load_yaml_config") as mock_load:
            mock_load.return_value = {"backend": {"url": "not-a-url"}}

            with pytest.raises(ValueError, match="Configuration validation failed"):
                load_config()


class TestGetConfig:
    """Test get_config function."""

    @patch("talk2me_ui.config._config", None)
    def test_get_config_first_call(self):
        """Test getting config on first call."""
        with patch("talk2me_ui.config.load_config") as mock_load:
            mock_config = Config()
            mock_load.return_value = mock_config

            result = get_config()

            assert result is mock_config
            mock_load.assert_called_once()

    @patch("talk2me_ui.config._config")
    def test_get_config_cached(self, mock_cached_config):
        """Test getting cached config."""
        mock_cached_config.isinstance = Config  # Mock isinstance check

        with patch("talk2me_ui.config.load_config") as mock_load:
            result = get_config()

            assert result is mock_cached_config
            mock_load.assert_not_called()


class TestReloadConfig:
    """Test reload_config function."""

    @patch("talk2me_ui.config._config", None)
    def test_reload_config(self):
        """Test reloading configuration."""
        with patch("talk2me_ui.config.load_config") as mock_load:
            mock_config = Config()
            mock_load.return_value = mock_config

            result = reload_config()

            assert result is mock_config
            mock_load.assert_called_once()

    @patch("talk2me_ui.config._config", None)
    def test_reload_config_with_paths(self):
        """Test reloading with custom paths."""
        with patch("talk2me_ui.config.load_config") as mock_load:
            mock_config = Config()
            mock_load.return_value = mock_config

            default_path = Path("/custom/default.yaml")
            user_path = Path("/custom/user.yaml")

            result = reload_config(default_path, user_path)

            assert result is mock_config
            mock_load.assert_called_once_with(default_path, user_path)
