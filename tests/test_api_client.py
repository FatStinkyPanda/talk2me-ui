"""Unit and integration tests for API client functionality."""

from io import BytesIO
from unittest.mock import Mock, patch

import pytest
from requests.exceptions import RequestException

from talk2me_ui.api_client import Talk2MeAPIClient


class TestTalk2MeAPIClient:
    """Test Talk2MeAPIClient class."""

    @pytest.fixture
    def client(self):
        """Create API client instance."""
        return Talk2MeAPIClient(base_url="http://test-api.com")

    @pytest.fixture
    def mock_response(self):
        """Create mock response object."""
        response = Mock()
        response.json.return_value = {"status": "ok"}
        response.content = b"test audio data"
        return response

    def test_init_with_base_url(self):
        """Test initialization with custom base URL."""
        client = Talk2MeAPIClient(base_url="http://custom-api.com")
        assert client.base_url == "http://custom-api.com"

    def test_init_without_base_url(self):
        """Test initialization without base URL (uses config)."""
        with patch("talk2me_ui.api_client.get_config") as mock_config:
            mock_config.return_value.backend.url = "http://config-api.com"
            client = Talk2MeAPIClient()
            assert client.base_url == "http://config-api.com"

    def test_make_request_success(self, client, mock_response):
        """Test successful request making."""
        with patch.object(client.session, "request") as mock_request:
            mock_request.return_value = mock_response

            response = client._make_request("GET", "/test")

            assert response == mock_response
            mock_request.assert_called_once_with("GET", "http://test-api.com/test", **{})

    def test_make_request_with_params(self, client, mock_response):
        """Test request with additional parameters."""
        with patch.object(client.session, "request") as mock_request:
            mock_request.return_value = mock_response

            client._make_request(
                "POST", "/test", json={"data": "test"}, headers={"X-Test": "value"}
            )

            mock_request.assert_called_once_with(
                "POST",
                "http://test-api.com/test",
                json={"data": "test"},
                headers={"X-Test": "value"},
            )

    def test_make_request_failure(self, client):
        """Test request failure."""
        with patch.object(client.session, "request") as mock_request:
            mock_request.side_effect = RequestException("Network error")

            with pytest.raises(RequestException, match="API request failed"):
                client._make_request("GET", "/test")

    def test_make_request_http_error(self, client):
        """Test HTTP error response."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = RequestException("404 Client Error")

        with patch.object(client.session, "request") as mock_request:
            mock_request.return_value = mock_response

            with pytest.raises(RequestException, match="API request failed"):
                client._make_request("GET", "/test")

    def test_parse_json_response_success(self, client, mock_response):
        """Test successful JSON parsing."""
        result = client._parse_json_response(mock_response)
        assert result == {"status": "ok"}
        mock_response.json.assert_called_once()

    def test_parse_json_response_failure(self, client, mock_response):
        """Test JSON parsing failure."""
        mock_response.json.side_effect = ValueError("Invalid JSON")

        with pytest.raises(ValueError, match="Invalid JSON response"):
            client._parse_json_response(mock_response)

    def test_health_check(self, client, mock_response):
        """Test health check endpoint."""
        with (
            patch.object(client, "_make_request") as mock_make_request,
            patch.object(client, "_parse_json_response") as mock_parse,
        ):
            mock_make_request.return_value = mock_response
            mock_parse.return_value = {"status": "healthy"}

            result = client.health_check()

            assert result == {"status": "healthy"}
            mock_make_request.assert_called_once_with("GET", "/")

    def test_stt_transcribe(self, client, mock_response):
        """Test speech-to-text transcription."""
        audio_data = b"fake audio data"
        audio_file = BytesIO(audio_data)

        with (
            patch.object(client, "_make_request") as mock_make_request,
            patch.object(client, "_parse_json_response") as mock_parse,
        ):
            mock_make_request.return_value = mock_response
            mock_parse.return_value = {"text": "Hello world"}

            result = client.stt_transcribe(audio_file, sample_rate=16000)

            assert result == {"text": "Hello world"}
            mock_make_request.assert_called_once_with(
                "POST", "/stt", files={"file": audio_file}, params={"sample_rate": 16000}
            )

    def test_stt_transcribe_no_sample_rate(self, client, mock_response):
        """Test STT without sample rate."""
        audio_file = BytesIO(b"audio")

        with (
            patch.object(client, "_make_request") as mock_make_request,
            patch.object(client, "_parse_json_response") as mock_parse,
        ):
            mock_make_request.return_value = mock_response
            mock_parse.return_value = {"text": "Test"}

            result = client.stt_transcribe(audio_file)

            assert result == {"text": "Test"}
            # Check that params doesn't include sample_rate
            call_args = mock_make_request.call_args
            assert "sample_rate" not in call_args[1]["params"]

    def test_tts_synthesize(self, client, mock_response):
        """Test text-to-speech synthesis."""
        mock_response.content = b"audio data"

        with patch.object(client, "_make_request") as mock_make_request:
            mock_make_request.return_value = mock_response

            result = client.tts_synthesize("Hello world", "voice1", speed=1.2)

            assert result == b"audio data"
            mock_make_request.assert_called_once_with(
                "POST", "/tts", json={"text": "Hello world", "voice": "voice1", "speed": 1.2}
            )

    def test_tts_synthesize_empty_text(self, client):
        """Test TTS with empty text."""
        with pytest.raises(ValueError, match="Text cannot be empty"):
            client.tts_synthesize("", "voice1")

    def test_tts_synthesize_whitespace_text(self, client):
        """Test TTS with whitespace-only text."""
        with pytest.raises(ValueError, match="Text cannot be empty"):
            client.tts_synthesize("   ", "voice1")

    def test_tts_synthesize_async(self, client, mock_response):
        """Test asynchronous TTS synthesis."""
        with (
            patch.object(client, "_make_request") as mock_make_request,
            patch.object(client, "_parse_json_response") as mock_parse,
        ):
            mock_make_request.return_value = mock_response
            mock_parse.return_value = {"task_id": "task123"}

            result = client.tts_synthesize_async("Hello", "voice1", pitch=5)

            assert result == {"task_id": "task123"}
            mock_make_request.assert_called_once_with(
                "POST", "/tts/async", json={"text": "Hello", "voice": "voice1", "pitch": 5}
            )

    def test_tts_get_status(self, client, mock_response):
        """Test getting TTS task status."""
        with (
            patch.object(client, "_make_request") as mock_make_request,
            patch.object(client, "_parse_json_response") as mock_parse,
        ):
            mock_make_request.return_value = mock_response
            mock_parse.return_value = {"status": "completed"}

            result = client.tts_get_status("task123")

            assert result == {"status": "completed"}
            mock_make_request.assert_called_once_with("GET", "/tts/status/task123")

    def test_list_voices(self, client, mock_response):
        """Test listing voices."""
        with (
            patch.object(client, "_make_request") as mock_make_request,
            patch.object(client, "_parse_json_response") as mock_parse,
        ):
            mock_make_request.return_value = mock_response
            mock_parse.return_value = {"voices": ["voice1", "voice2"]}

            result = client.list_voices()

            assert result == {"voices": ["voice1", "voice2"]}
            mock_make_request.assert_called_once_with("GET", "/voices")

    def test_create_voice(self, client, mock_response):
        """Test creating a voice."""
        samples = [BytesIO(b"sample1"), BytesIO(b"sample2")]

        with (
            patch.object(client, "_make_request") as mock_make_request,
            patch.object(client, "_parse_json_response") as mock_parse,
        ):
            mock_make_request.return_value = mock_response
            mock_parse.return_value = {"voice_id": "voice123"}

            result = client.create_voice("Test Voice", "en", samples)

            assert result == {"voice_id": "voice123"}
            # Verify files are included in request
            call_args = mock_make_request.call_args
            assert "files" in call_args[1]
            assert "data" in call_args[1]

    def test_create_voice_empty_name(self, client):
        """Test creating voice with empty name."""
        with pytest.raises(ValueError, match="Voice name cannot be empty"):
            client.create_voice("", "en")

    def test_delete_voice(self, client, mock_response):
        """Test deleting a voice."""
        with (
            patch.object(client, "_make_request") as mock_make_request,
            patch.object(client, "_parse_json_response") as mock_parse,
        ):
            mock_make_request.return_value = mock_response
            mock_parse.return_value = {"deleted": True}

            result = client.delete_voice("voice123")

            assert result == {"deleted": True}
            mock_make_request.assert_called_once_with("DELETE", "/voices/voice123")

    def test_delete_voice_empty_id(self, client):
        """Test deleting voice with empty ID."""
        with pytest.raises(ValueError, match="Voice ID cannot be empty"):
            client.delete_voice("")

    def test_clone_voice(self, client, mock_response):
        """Test cloning a voice."""
        samples = [BytesIO(b"sample")]

        with (
            patch.object(client, "_make_request") as mock_make_request,
            patch.object(client, "_parse_json_response") as mock_parse,
        ):
            mock_make_request.return_value = mock_response
            mock_parse.return_value = {"cloned_voice_id": "voice456"}

            result = client.clone_voice("voice123", samples)

            assert result == {"cloned_voice_id": "voice456"}
            mock_make_request.assert_called_once_with(
                "POST", "/voices/voice123/samples", files=[("samples", samples[0])]
            )

    def test_clone_voice_empty_id(self, client):
        """Test cloning voice with empty ID."""
        with pytest.raises(ValueError, match="Voice ID cannot be empty"):
            client.clone_voice("", [BytesIO(b"data")])

    def test_clone_voice_no_samples(self, client):
        """Test cloning voice without samples."""
        with pytest.raises(ValueError, match="At least one sample file is required"):
            client.clone_voice("voice123", [])

    def test_update_voice(self, client, mock_response):
        """Test updating a voice."""
        with (
            patch.object(client, "_make_request") as mock_make_request,
            patch.object(client, "_parse_json_response") as mock_parse,
        ):
            mock_make_request.return_value = mock_response
            mock_parse.return_value = {"updated": True}

            result = client.update_voice("voice123", name="New Name", language="es")

            assert result == {"updated": True}
            mock_make_request.assert_called_once_with(
                "PUT", "/voices/voice123", json={"name": "New Name", "language": "es"}
            )

    def test_update_voice_partial_update(self, client, mock_response):
        """Test updating voice with only name."""
        with (
            patch.object(client, "_make_request") as mock_make_request,
            patch.object(client, "_parse_json_response") as mock_parse,
        ):
            mock_make_request.return_value = mock_response
            mock_parse.return_value = {"updated": True}

            result = client.update_voice("voice123", name="New Name")

            assert result == {"updated": True}
            mock_make_request.assert_called_once_with(
                "PUT", "/voices/voice123", json={"name": "New Name"}
            )

    def test_update_voice_empty_id(self, client):
        """Test updating voice with empty ID."""
        with pytest.raises(ValueError, match="Voice ID cannot be empty"):
            client.update_voice("", name="New Name")

    def test_update_voice_no_fields(self, client):
        """Test updating voice with no fields provided."""
        with pytest.raises(ValueError, match="At least one field must be provided"):
            client.update_voice("voice123")

    def test_create_voice_no_samples(self, client, mock_response):
        """Test creating voice without samples."""
        with (
            patch.object(client, "_make_request") as mock_make_request,
            patch.object(client, "_parse_json_response") as mock_parse,
        ):
            mock_make_request.return_value = mock_response
            mock_parse.return_value = {"voice_id": "voice123"}

            result = client.create_voice("Test Voice", "en")

            assert result == {"voice_id": "voice123"}
            call_args = mock_make_request.call_args
            assert call_args[1]["data"] == {"name": "Test Voice", "language": "en"}
            assert "files" not in call_args[1] or call_args[1]["files"] == []

    def test_tts_synthesize_async_empty_text(self, client):
        """Test async TTS with empty text."""
        with pytest.raises(ValueError, match="Text cannot be empty"):
            client.tts_synthesize_async("", "voice1")

    def test_tts_synthesize_async_whitespace_text(self, client):
        """Test async TTS with whitespace-only text."""
        with pytest.raises(ValueError, match="Text cannot be empty"):
            client.tts_synthesize_async("   ", "voice1")

    def test_generate_audiobook(self, client, mock_response):
        """Test audiobook generation."""
        mock_response.content = b"audiobook data"

        with patch.object(client, "_make_request") as mock_make_request:
            mock_make_request.return_value = mock_response

            result = client.generate_audiobook("Book text", "voice1", format="mp3")

            assert result == b"audiobook data"
            mock_make_request.assert_called_once_with(
                "POST", "/audiobook", json={"text": "Book text", "voice": "voice1", "format": "mp3"}
            )

    def test_generate_audiobook_empty_text(self, client):
        """Test audiobook generation with empty text."""
        with pytest.raises(ValueError, match="Text cannot be empty"):
            client.generate_audiobook("", "voice1")

    def test_list_sound_effects(self, client, mock_response):
        """Test listing sound effects."""
        with (
            patch.object(client, "_make_request") as mock_make_request,
            patch.object(client, "_parse_json_response") as mock_parse,
        ):
            mock_make_request.return_value = mock_response
            mock_parse.return_value = {"effects": ["effect1", "effect2"]}

            result = client.list_sound_effects()

            assert result == {"effects": ["effect1", "effect2"]}
            mock_make_request.assert_called_once_with("GET", "/sound-effects")

    def test_upload_sound_effect(self, client, mock_response):
        """Test uploading sound effect."""
        audio_file = BytesIO(b"audio data")

        with (
            patch.object(client, "_make_request") as mock_make_request,
            patch.object(client, "_parse_json_response") as mock_parse,
        ):
            mock_make_request.return_value = mock_response
            mock_parse.return_value = {"effect_id": "effect123"}

            result = client.upload_sound_effect("test_effect", audio_file, category="test")

            assert result == {"effect_id": "effect123"}
            call_args = mock_make_request.call_args
            assert call_args[1]["data"]["name"] == "test_effect"
            assert call_args[1]["data"]["category"] == "test"

    def test_upload_sound_effect_empty_name(self, client):
        """Test uploading sound effect with empty name."""
        with pytest.raises(ValueError, match="Sound effect name cannot be empty"):
            client.upload_sound_effect("", BytesIO(b"data"))

    def test_list_background_audio(self, client, mock_response):
        """Test listing background audio."""
        with (
            patch.object(client, "_make_request") as mock_make_request,
            patch.object(client, "_parse_json_response") as mock_parse,
        ):
            mock_make_request.return_value = mock_response
            mock_parse.return_value = {"backgrounds": ["bg1", "bg2"]}

            result = client.list_background_audio()

            assert result == {"backgrounds": ["bg1", "bg2"]}
            mock_make_request.assert_called_once_with("GET", "/background-audio")

    def test_upload_background_audio(self, client, mock_response):
        """Test uploading background audio."""
        audio_file = BytesIO(b"bg audio")

        with (
            patch.object(client, "_make_request") as mock_make_request,
            patch.object(client, "_parse_json_response") as mock_parse,
        ):
            mock_make_request.return_value = mock_response
            mock_parse.return_value = {"background_id": "bg123"}

            result = client.upload_background_audio("test_bg", audio_file, type="ambient")

            assert result == {"background_id": "bg123"}
            call_args = mock_make_request.call_args
            assert call_args[1]["data"]["name"] == "test_bg"
            assert call_args[1]["data"]["type"] == "ambient"

    def test_upload_background_audio_empty_name(self, client):
        """Test uploading background audio with empty name."""
        with pytest.raises(ValueError, match="Background audio name cannot be empty"):
            client.upload_background_audio("", BytesIO(b"data"))


class TestAPIClientIntegration:
    """Integration tests for API client (would require actual backend)."""

    @pytest.mark.integration
    def test_health_check_integration(self):
        """Integration test for health check (requires running backend)."""
        # This would test against a real backend
        # client = Talk2MeAPIClient("http://localhost:8000")
        # result = client.health_check()
        # assert "status" in result
        pass

    @pytest.mark.integration
    def test_list_voices_integration(self):
        """Integration test for listing voices."""
        # Similar to above
        pass
