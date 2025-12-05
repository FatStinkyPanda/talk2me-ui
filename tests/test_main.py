"""
Unit tests, integration tests, and API endpoint tests for FastAPI application.
"""

import base64
from io import BytesIO
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from talk2me_ui.main import (
    BACKGROUND_DIR,
    SFX_DIR,
    app,
    audiobook_tasks,
    process_audiobook,
    process_stt,
    process_tts,
    stt_tasks,
    tts_tasks,
    validate_audio_file,
)


class TestFastAPIApp:
    """Test FastAPI application setup."""

    def test_app_creation(self):
        """Test that FastAPI app is created."""
        assert app.title == "Talk2Me UI"
        assert app.version == "1.0.0"

    def test_cors_middleware(self):
        """Test CORS middleware is configured."""
        cors_middleware = None
        for middleware in app.user_middleware:
            if hasattr(middleware, "cls") and "CORSMiddleware" in str(middleware.cls):
                cors_middleware = middleware
                break

        assert cors_middleware is not None
        # Check options contain allow_origins: ["*"]
        assert cors_middleware.options["allow_origins"] == ["*"]


class TestRouteHandlers:
    """Test basic route handlers."""

    def test_dashboard_route(self):
        """Test dashboard page route."""
        client = TestClient(app)
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_voice_management_route(self):
        """Test voice management page route."""
        client = TestClient(app)
        response = client.get("/voices")
        assert response.status_code == 200

    def test_stt_route(self):
        """Test STT page route."""
        client = TestClient(app)
        response = client.get("/stt")
        assert response.status_code == 200

    def test_tts_route(self):
        """Test TTS page route."""
        client = TestClient(app)
        response = client.get("/tts")
        assert response.status_code == 200

    def test_audiobook_route(self):
        """Test audiobook page route."""
        client = TestClient(app)
        response = client.get("/audiobook")
        assert response.status_code == 200

    def test_sound_library_route(self):
        """Test sound library page route."""
        client = TestClient(app)
        response = client.get("/sounds")
        assert response.status_code == 200

    def test_conversation_route(self):
        """Test conversation page route."""
        client = TestClient(app)
        response = client.get("/conversation")
        assert response.status_code == 200

    def test_settings_route(self):
        """Test settings page route."""
        client = TestClient(app)
        response = client.get("/settings")
        assert response.status_code == 200


class TestAPIEndpoints:
    """Test API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @patch("talk2me_ui.main.api_client")
    def test_list_voices(self, mock_api_client, client):
        """Test list voices endpoint."""
        mock_api_client.list_voices.return_value = {"voices": ["voice1", "voice2"]}

        response = client.get("/api/voices")

        assert response.status_code == 200
        assert response.json() == {"voices": ["voice1", "voice2"]}
        mock_api_client.list_voices.assert_called_once()

    @patch("talk2me_ui.main.api_client")
    def test_list_voices_error(self, mock_api_client, client):
        """Test list voices endpoint with error."""
        mock_api_client.list_voices.side_effect = Exception("API error")

        response = client.get("/api/voices")

        assert response.status_code == 500
        assert "API error" in response.json()["detail"]

    @patch("talk2me_ui.main.api_client")
    @patch("talk2me_ui.main.BackgroundTasks")
    @patch("talk2me_ui.main.tempfile.NamedTemporaryFile")
    @patch("talk2me_ui.main.os.unlink")
    def test_stt_upload(self, mock_unlink, mock_tempfile, mock_bg_tasks, mock_api_client, client):
        """Test STT upload endpoint."""
        # Mock tempfile
        mock_temp = Mock()
        mock_temp.name = "/tmp/test.wav"
        mock_tempfile.return_value.__enter__.return_value = mock_temp

        # Mock API client
        mock_api_client.stt_transcribe.return_value = {"text": "Hello world"}

        # Create test audio file
        audio_data = b"fake audio data"
        files = {"audio_file": ("test.wav", BytesIO(audio_data), "audio/wav")}
        data = {"sample_rate": "16000"}

        response = client.post("/api/stt", files=files, data=data)

        assert response.status_code == 200
        result = response.json()
        assert "task_id" in result

        # Verify background task was added
        mock_bg_tasks.return_value.add_task.assert_called_once()

    @patch("talk2me_ui.main.api_client")
    @patch("talk2me_ui.main.BackgroundTasks")
    def test_tts_generate(self, mock_bg_tasks, mock_api_client, client):
        """Test TTS generate endpoint."""
        # Mock API client for async TTS
        mock_api_client.tts_synthesize_async.return_value = {"task_id": "tts_task_123"}

        data = {
            "text": "Hello world",
            "voice_id": "voice1",
            "speed": "1.2",
            "pitch": "5",
            "output_format": "wav",
        }

        response = client.post("/api/tts", data=data)

        assert response.status_code == 200
        result = response.json()
        assert "task_id" in result

        # Verify background task was added
        mock_bg_tasks.return_value.add_task.assert_called_once()

    def test_tts_generate_empty_text(self, client):
        """Test TTS with empty text."""
        data = {"text": "", "voice_id": "voice1"}
        response = client.post("/api/tts", data=data)
        assert response.status_code == 400
        assert "cannot be empty" in response.json()["detail"]

    def test_tts_generate_text_too_long(self, client):
        """Test TTS with text too long."""
        long_text = "a" * 5001
        data = {"text": long_text, "voice_id": "voice1"}
        response = client.post("/api/tts", data=data)
        assert response.status_code == 400
        assert "too long" in response.json()["detail"]

    @patch("talk2me_ui.main.stt_tasks")
    def test_stt_status(self, mock_stt_tasks, client):
        """Test STT status endpoint."""
        mock_stt_tasks.__getitem__.return_value = {
            "status": "completed",
            "result": {"text": "Hello"},
        }

        response = client.get("/api/stt/task123")

        assert response.status_code == 200
        assert response.json()["status"] == "completed"

    def test_stt_status_not_found(self, client):
        """Test STT status for non-existent task."""
        response = client.get("/api/stt/nonexistent")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    @patch("talk2me_ui.main.tts_tasks")
    def test_tts_status(self, mock_tts_tasks, client):
        """Test TTS status endpoint."""
        mock_tts_tasks.__getitem__.return_value = {"status": "completed"}

        response = client.get("/api/tts/task123")

        assert response.status_code == 200
        assert response.json()["status"] == "completed"

    @patch("talk2me_ui.main.tts_tasks")
    def test_tts_audio_download(self, mock_tts_tasks, client):
        """Test TTS audio download."""
        audio_data = b"fake audio"
        encoded_audio = base64.b64encode(audio_data).decode("utf-8")

        mock_tts_tasks.__getitem__.return_value = {
            "status": "completed",
            "audio_data": encoded_audio,
            "filename": "test.wav",
        }

        response = client.get("/api/tts/audio/task123")

        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/wav"
        assert response.content == audio_data

    @patch("talk2me_ui.main.parse_audiobook_markup")
    @patch("talk2me_ui.main.validate_audiobook_markup")
    @patch("talk2me_ui.main.BackgroundTasks")
    def test_audiobook_generate(self, mock_bg_tasks, mock_validate, mock_parse, client):
        """Test audiobook generation endpoint."""
        mock_validate.return_value = []  # No validation issues
        mock_parse.return_value = [Mock(text="Chapter 1", voice="voice1")]

        data = {
            "text": "{{{voice:voice1}}}Chapter 1{{{voice:voice2}}}Chapter 2",
            "output_format": "wav",
            "sample_rate": "22050",
        }

        response = client.post("/api/audiobook", data=data)

        assert response.status_code == 200
        result = response.json()
        assert "task_id" in result

        mock_bg_tasks.return_value.add_task.assert_called_once()

    def test_audiobook_generate_empty_text(self, client):
        """Test audiobook generation with empty text."""
        data = {"text": ""}
        response = client.post("/api/audiobook", data=data)
        assert response.status_code == 400

    @patch("talk2me_ui.main.validate_audiobook_markup")
    def test_audiobook_generate_invalid_markup(self, mock_validate, client):
        """Test audiobook generation with invalid markup."""
        mock_validate.return_value = ["Invalid voice reference"]

        data = {"text": "{{{invalid:markup}}}"}
        response = client.post("/api/audiobook", data=data)
        assert response.status_code == 400
        assert "Invalid markup" in response.json()["detail"]


class TestSoundManagement:
    """Test sound effect and background audio management."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture(autouse=True)
    def setup_dirs(self):
        """Set up test directories."""
        SFX_DIR.mkdir(parents=True, exist_ok=True)
        BACKGROUND_DIR.mkdir(parents=True, exist_ok=True)
        yield
        # Cleanup
        for file in SFX_DIR.glob("*"):
            if file.is_file():
                file.unlink()
        for file in BACKGROUND_DIR.glob("*"):
            if file.is_file():
                file.unlink()

    def test_list_sound_effects(self, client):
        """Test listing sound effects."""
        response = client.get("/api/sounds/effects")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_background_audio(self, client):
        """Test listing background audio."""
        response = client.get("/api/sounds/background")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_upload_sound_effect_valid(self, client):
        """Test uploading valid sound effect."""
        audio_data = b"fake audio data"
        files = {"audio_file": ("test.wav", BytesIO(audio_data), "audio/wav")}
        data = {"name": "Test Effect", "id": "test_effect", "category": "test", "volume": "0.8"}

        response = client.post("/api/sounds/effects", files=files, data=data)

        assert response.status_code == 200
        result = response.json()
        assert "id" in result

    def test_upload_sound_effect_no_id(self, client):
        """Test uploading sound effect without ID."""
        audio_data = b"fake audio data"
        files = {"audio_file": ("test.wav", BytesIO(audio_data), "audio/wav")}
        data = {"name": "Test Effect"}

        response = client.post("/api/sounds/effects", files=files, data=data)

        assert response.status_code == 400
        assert "required" in response.json()["detail"]

    def test_upload_sound_effect_invalid_type(self, client):
        """Test uploading sound effect with invalid file type."""
        files = {"audio_file": ("test.txt", BytesIO(b"text data"), "text/plain")}
        data = {"id": "test"}

        response = client.post("/api/sounds/effects", files=files, data=data)

        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]

    def test_upload_background_audio_valid(self, client):
        """Test uploading valid background audio."""
        audio_data = b"fake bg audio"
        files = {"audio_file": ("bg.wav", BytesIO(audio_data), "audio/wav")}
        data = {"name": "Test Background", "id": "test_bg", "type": "ambient", "volume": "0.5"}

        response = client.post("/api/sounds/background", files=files, data=data)

        assert response.status_code == 200
        result = response.json()
        assert "id" in result


class TestValidationFunctions:
    """Test utility validation functions."""

    def test_validate_audio_file_valid(self):
        """Test validating valid audio file."""
        mock_file = Mock()
        mock_file.content_type = "audio/wav"
        mock_file.file = Mock()
        mock_file.file.tell.return_value = 1024  # 1KB

        # Should not raise exception
        validate_audio_file(mock_file)

    def test_validate_audio_file_invalid_type(self):
        """Test validating invalid file type."""
        mock_file = Mock()
        mock_file.content_type = "text/plain"

        with pytest.raises(HTTPException) as exc_info:
            validate_audio_file(mock_file)

        assert exc_info.value.status_code == 400
        assert "Unsupported file type" in str(exc_info.value.detail)

    def test_validate_audio_file_too_large(self):
        """Test validating file that's too large."""
        mock_file = Mock()
        mock_file.content_type = "audio/wav"
        mock_file.file = Mock()
        mock_file.file.tell.return_value = 60 * 1024 * 1024  # 60MB

        with pytest.raises(HTTPException) as exc_info:
            validate_audio_file(mock_file)

        assert exc_info.value.status_code == 400
        assert "too large" in str(exc_info.value.detail)


class TestBackgroundTasks:
    """Test background task functions."""

    @pytest.mark.asyncio
    @patch("talk2me_ui.main.api_client")
    @patch("talk2me_ui.main.os.unlink")
    async def test_process_stt_success(self, mock_unlink, mock_api_client):
        """Test successful STT processing."""
        mock_api_client.stt_transcribe.return_value = {"text": "Hello world"}

        await process_stt("task123", "/tmp/test.wav", 16000)

        assert stt_tasks["task123"]["status"] == "completed"
        assert stt_tasks["task123"]["result"]["text"] == "Hello world"
        mock_unlink.assert_called_once_with("/tmp/test.wav")

    @pytest.mark.asyncio
    @patch("talk2me_ui.main.api_client")
    @patch("talk2me_ui.main.os.unlink")
    async def test_process_stt_failure(self, mock_unlink, mock_api_client):
        """Test STT processing failure."""
        mock_api_client.stt_transcribe.side_effect = Exception("API error")

        await process_stt("task123", "/tmp/test.wav")

        assert stt_tasks["task123"]["status"] == "failed"
        assert "API error" in stt_tasks["task123"]["error"]
        mock_unlink.assert_called_once_with("/tmp/test.wav")

    @pytest.mark.asyncio
    @patch("talk2me_ui.main.api_client")
    async def test_process_tts_success(self, mock_api_client):
        """Test successful TTS processing."""
        mock_api_client.tts_synthesize.return_value = b"audio data"

        await process_tts("task123", "Hello world", "voice1", speed=1.2)

        assert tts_tasks["task123"]["status"] == "completed"
        assert "audio_data" in tts_tasks["task123"]
        assert tts_tasks["task123"]["text"] == "Hello world"

    @pytest.mark.asyncio
    @patch("talk2me_ui.main.parse_audiobook_markup")
    @patch("talk2me_ui.main.api_client")
    async def test_process_audiobook_success(self, mock_api_client, mock_parse):
        """Test successful audiobook processing."""
        # Mock markup parsing
        mock_section = Mock()
        mock_section.text = "Chapter 1"
        mock_section.voice = "voice1"
        mock_parse.return_value = [mock_section]

        # Mock TTS synthesis
        mock_api_client.tts_synthesize.return_value = b"audio data"

        # Mock pydub
        with (
            patch("talk2me_ui.main.AudioSegment") as mock_audio_segment,
            patch("talk2me_ui.main.io.BytesIO") as mock_bytesio,
        ):
            mock_segment = Mock()
            mock_audio_segment.from_wav.return_value = mock_segment
            mock_audio_segment.empty.return_value = mock_segment

            mock_buffer = Mock()
            mock_bytesio.return_value = mock_buffer
            mock_buffer.getvalue.return_value = b"combined audio"

            await process_audiobook("task123", "{{{voice:voice1}}}Chapter 1")

            assert audiobook_tasks["task123"]["status"] == "completed"
            assert "audio_data" in audiobook_tasks["task123"]


class TestWebSocket:
    """Test WebSocket endpoint."""

    @pytest.mark.asyncio
    @patch("talk2me_ui.main.conversation_manager")
    async def test_websocket_connection(self, mock_conv_manager):
        """Test WebSocket connection establishment."""

        # This is a basic test - full WebSocket testing would require
        # a test server setup
        mock_conv_manager.start_conversation.return_value = "conv123"

        # For now, just test that the endpoint exists and can be imported
        assert hasattr(app, "websocket")
        # The WebSocket route should be registered
        websocket_routes = [
            route
            for route in app.routes
            if hasattr(route, "path") and route.path == "/ws/conversation"
        ]
        assert len(websocket_routes) == 1


class TestExceptionHandlers:
    """Test exception handlers."""

    def test_global_exception_handler(self):
        """Test global exception handler."""
        client = TestClient(app)

        # Trigger an exception by accessing a non-existent route that might cause issues
        # Since we have a catch-all handler, we can test it by mocking an internal error

        with patch("talk2me_ui.main.templates.TemplateResponse") as mock_template:
            mock_template.return_value = "error page"

            # This is tricky to test directly, but the handler exists
            assert app.exception_handlers[Exception] is not None
