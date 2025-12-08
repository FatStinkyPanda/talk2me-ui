"""Unit tests for conversation manager WebSocket handling."""

import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest
from websockets.exceptions import ConnectionClosedError

from talk2me_ui.api_client import Talk2MeAPIClient
from talk2me_ui.conversation_manager import (
    ConversationManager,
    ConversationSession,
    conversation_manager,
)


class TestConversationManager:
    """Test ConversationManager class."""

    @pytest.fixture
    def manager(self):
        """Create conversation manager instance."""
        return ConversationManager(backend_url="ws://test-backend.com/ws")

    def test_init_without_backend_url(self):
        """Test initialization without backend URL (uses config)."""
        with patch("talk2me_ui.conversation_manager.get_config") as mock_config:
            mock_config.return_value.backend.url = "http://backend.com"
            manager = ConversationManager()
            assert manager.backend_url == "ws://backend.com/ws"
            assert isinstance(manager.api_client, Talk2MeAPIClient)

    @pytest.mark.asyncio
    @patch("talk2me_ui.conversation_manager.websockets.connect")
    async def test_start_conversation(self, mock_ws_connect, manager):
        """Test starting a new conversation."""
        mock_websocket = AsyncMock()
        mock_ws_connect.return_value = mock_websocket

        frontend_ws = AsyncMock()

        conversation_id = await manager.start_conversation(frontend_ws)

        assert conversation_id in manager.active_conversations
        assert conversation_id in manager.frontend_connections
        assert frontend_ws in manager.frontend_connections[conversation_id]

        # Verify session was created and started
        session = manager.active_conversations[conversation_id]
        assert isinstance(session, ConversationSession)
        assert session.conversation_id == conversation_id

    @pytest.mark.asyncio
    async def test_end_conversation(self, manager):
        """Test ending a conversation."""
        # Set up a conversation
        frontend_ws = AsyncMock()
        conversation_id = await manager.start_conversation(frontend_ws)

        # End the conversation
        await manager.end_conversation(conversation_id)

        assert conversation_id not in manager.active_conversations
        assert conversation_id not in manager.frontend_connections

        # Verify WebSocket was closed
        frontend_ws.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_end_nonexistent_conversation(self, manager):
        """Test ending a non-existent conversation."""
        # Should not raise an error
        await manager.end_conversation("nonexistent")
        assert True  # If we get here, no exception was raised

    @pytest.mark.asyncio
    async def test_handle_frontend_message_audio_data(self, manager):
        """Test handling audio data message."""
        # Set up conversation
        frontend_ws = AsyncMock()
        conversation_id = await manager.start_conversation(frontend_ws)

        session = manager.active_conversations[conversation_id]
        session.send_audio_to_backend = AsyncMock()

        # Audio data as base64 encoded string in JSON
        import base64

        audio_data = b"fake audio data"
        encoded_audio = base64.b64encode(audio_data).decode("utf-8")

        message = json.dumps({"type": "audio_data", "audio": encoded_audio})

        await manager.handle_frontend_message(conversation_id, frontend_ws, message)

        # Currently the code passes the string directly, not decoded bytes
        # This test documents the current behavior
        session.send_audio_to_backend.assert_called_once_with(encoded_audio)

    @pytest.mark.asyncio
    async def test_handle_frontend_message_start_recording(self, manager):
        """Test handling start recording message."""
        frontend_ws = AsyncMock()
        conversation_id = await manager.start_conversation(frontend_ws)

        session = manager.active_conversations[conversation_id]

        message = json.dumps({"type": "start_recording"})

        await manager.handle_frontend_message(conversation_id, frontend_ws, message)

        assert session.recording_active is True
        # Verify broadcast was called (would need to check the broadcast method)

    @pytest.mark.asyncio
    async def test_handle_frontend_message_stop_recording(self, manager):
        """Test handling stop recording message."""
        frontend_ws = AsyncMock()
        conversation_id = await manager.start_conversation(frontend_ws)

        session = manager.active_conversations[conversation_id]
        session.recording_active = True

        message = json.dumps({"type": "stop_recording"})

        await manager.handle_frontend_message(conversation_id, frontend_ws, message)

        assert session.recording_active is False

    @pytest.mark.asyncio
    async def test_handle_frontend_message_wake_word_detected(self, manager):
        """Test handling wake word detected message."""
        frontend_ws = AsyncMock()
        conversation_id = await manager.start_conversation(frontend_ws)

        message = json.dumps({"type": "wake_word_detected"})

        await manager.handle_frontend_message(conversation_id, frontend_ws, message)

        assert manager.wake_word_active is True

    @pytest.mark.asyncio
    async def test_handle_frontend_message_unknown_type(self, manager):
        """Test handling unknown message type."""
        frontend_ws = AsyncMock()
        conversation_id = await manager.start_conversation(frontend_ws)

        message = json.dumps({"type": "unknown"})

        # Should not raise an error
        await manager.handle_frontend_message(conversation_id, frontend_ws, message)

    @pytest.mark.asyncio
    async def test_handle_frontend_message_invalid_json(self, manager):
        """Test handling invalid JSON message."""
        frontend_ws = AsyncMock()
        conversation_id = await manager.start_conversation(frontend_ws)

        message = "invalid json"

        # Should not raise an error (handled internally)
        await manager.handle_frontend_message(conversation_id, frontend_ws, message)

    @pytest.mark.asyncio
    async def test_broadcast_to_frontend(self, manager):
        """Test broadcasting messages to frontend."""
        frontend_ws1 = AsyncMock()
        frontend_ws2 = AsyncMock()

        conversation_id = "test_conv"
        manager.frontend_connections[conversation_id] = {frontend_ws1, frontend_ws2}

        message = {"type": "test", "data": "value"}

        await manager._broadcast_to_frontend(conversation_id, message)

        # Verify both WebSockets received the message
        expected_json = json.dumps(message)
        frontend_ws1.send.assert_called_once_with(expected_json)
        frontend_ws2.send.assert_called_once_with(expected_json)

    @pytest.mark.asyncio
    async def test_broadcast_to_frontend_send_failure(self, manager):
        """Test broadcasting when WebSocket send fails."""
        frontend_ws = AsyncMock()
        frontend_ws.send.side_effect = Exception("Send failed")

        conversation_id = "test_conv"
        manager.frontend_connections[conversation_id] = {frontend_ws}

        message = {"type": "test"}

        # Should not raise an error
        await manager._broadcast_to_frontend(conversation_id, message)

    @pytest.mark.asyncio
    async def test_remove_frontend_connection(self, manager):
        """Test removing a frontend connection."""
        frontend_ws1 = AsyncMock()
        frontend_ws2 = AsyncMock()

        conversation_id = "test_conv"
        manager.frontend_connections[conversation_id] = {frontend_ws1, frontend_ws2}

        await manager.remove_frontend_connection(conversation_id, frontend_ws1)

        assert frontend_ws1 not in manager.frontend_connections[conversation_id]
        assert frontend_ws2 in manager.frontend_connections[conversation_id]

    async def test_remove_frontend_connection_last_one(self, manager):
        """Test removing the last frontend connection ends conversation."""
        frontend_ws = AsyncMock()

        conversation_id = "test_conv"
        manager.frontend_connections[conversation_id] = {frontend_ws}
        manager.active_conversations[conversation_id] = Mock()

        with patch.object(manager, "end_conversation", new_callable=AsyncMock) as mock_end:
            await manager.remove_frontend_connection(conversation_id, frontend_ws)

            mock_end.assert_called_once_with(conversation_id)


class TestConversationSession:
    """Test ConversationSession class."""

    @pytest.fixture
    def manager(self):
        """Create mock conversation manager."""
        return Mock()

    @pytest.fixture
    def session(self, manager):
        """Create conversation session instance."""
        return ConversationSession("test_conv", "ws://test-backend.com/ws", manager)

    @pytest.mark.asyncio
    @patch("talk2me_ui.conversation_manager.websockets.connect", new_callable=AsyncMock)
    async def test_start_session(self, mock_ws_connect, session):
        """Test starting a conversation session."""
        mock_backend_ws = AsyncMock()
        mock_ws_connect.return_value = mock_backend_ws

        await session.start()

        assert session.is_active is True
        assert session.backend_ws == mock_backend_ws
        mock_ws_connect.assert_called_once_with("ws://test-backend.com/ws")

        # Stop the session to prevent infinite loop in background task
        await session.stop()

    @pytest.mark.asyncio
    async def test_start_session_no_backend_url(self, session):
        """Test starting session without backend URL."""
        session.backend_url = None

        await session.start()

        assert session.is_active is True
        assert session.backend_ws is None

    @pytest.mark.asyncio
    async def test_start_session_backend_connection_failure(self, session):
        """Test starting session with backend connection failure."""
        session.backend_url = "ws://bad-url.com/ws"

        with patch(
            "talk2me_ui.conversation_manager.websockets.connect",
            side_effect=Exception("Connection failed"),
        ):
            await session.start()

            assert session.is_active is True
            assert session.backend_ws is None

    @pytest.mark.asyncio
    async def test_stop_session(self, session):
        """Test stopping a conversation session."""
        mock_backend_ws = AsyncMock()
        session.backend_ws = mock_backend_ws
        session.is_active = True

        await session.stop()

        assert session.is_active is False
        mock_backend_ws.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_audio_to_backend_recording_active(self, session):
        """Test sending audio when recording is active."""
        session.recording_active = True
        session.backend_ws = AsyncMock()

        audio_data = b"test audio"

        await session.send_audio_to_backend(audio_data)

        session.backend_ws.send.assert_called_once_with(audio_data)

    @pytest.mark.asyncio
    async def test_send_audio_to_backend_recording_inactive(self, session):
        """Test sending audio when recording is inactive."""
        session.recording_active = False
        session.backend_ws = AsyncMock()

        audio_data = b"test audio"

        await session.send_audio_to_backend(audio_data)

        session.backend_ws.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_audio_to_backend_no_websocket(self, session):
        """Test sending audio without backend WebSocket."""
        session.backend_ws = None
        session.recording_active = True

        audio_data = b"test audio"

        # Should not raise an error
        await session.send_audio_to_backend(audio_data)

    @pytest.mark.asyncio
    async def test_listen_to_backend_transcription(self, session):
        """Test listening for transcription messages."""
        session.backend_ws = AsyncMock()
        session.backend_ws.recv.return_value = json.dumps(
            {"type": "transcription", "text": "Hello world", "confidence": 0.95}
        )
        session.is_active = True

        session._send_to_frontend = AsyncMock()

        # Mock the listening loop to run once
        with patch.object(asyncio, "create_task"):
            await session._listen_to_backend()

        session._send_to_frontend.assert_called_once_with(
            {"type": "transcription", "text": "Hello world", "confidence": 0.95}
        )

    @pytest.mark.asyncio
    async def test_listen_to_backend_tts_audio(self, session):
        """Test listening for TTS audio messages."""
        import base64

        session.backend_ws = AsyncMock()
        audio_data = b"audio data"
        encoded_audio = base64.b64encode(audio_data).decode("utf-8")
        session.backend_ws.recv.return_value = json.dumps(
            {"type": "tts_audio", "audio": encoded_audio}
        )
        session.is_active = True

        session._send_to_frontend = AsyncMock()

        with patch.object(asyncio, "create_task"):
            await session._listen_to_backend()

        session._send_to_frontend.assert_called_once_with(
            {"type": "tts_audio", "audio": encoded_audio}
        )

    @pytest.mark.asyncio
    async def test_listen_to_backend_wake_word(self, session):
        """Test listening for wake word messages."""
        session.backend_ws = AsyncMock()
        session.backend_ws.recv.return_value = json.dumps({"type": "wake_word_detected"})
        session.is_active = True

        session._send_to_frontend = AsyncMock()

        with patch.object(asyncio, "create_task"):
            await session._listen_to_backend()

        session._send_to_frontend.assert_called_once_with({"type": "wake_word_detected"})

    @pytest.mark.asyncio
    async def test_listen_to_backend_binary_audio(self, session):
        """Test listening for binary audio data."""
        session.backend_ws = AsyncMock()
        session.backend_ws.recv.return_value = b"raw audio data"
        session.is_active = True

        session._send_to_frontend = AsyncMock()

        with patch.object(asyncio, "create_task"):
            await session._listen_to_backend()

        session._send_to_frontend.assert_called_once_with(
            {"type": "audio_response", "audio": b"raw audio data"}
        )

    @pytest.mark.asyncio
    async def test_listen_to_backend_connection_closed(self, session):
        """Test handling connection closed."""
        session.backend_ws = AsyncMock()
        session.backend_ws.recv.side_effect = ConnectionClosedError(None, None)
        session.is_active = True

        with patch.object(asyncio, "create_task"):
            await session._listen_to_backend()

        assert session.backend_ws is None

    @pytest.mark.asyncio
    async def test_check_wake_word_detected(self, session):
        """Test wake word detection in transcription."""
        session.manager.wake_word_phrase = "hey computer"
        session._send_to_frontend = AsyncMock()

        await session._check_wake_word("Hey computer, what's the weather?")

        session._send_to_frontend.assert_called_once_with({"type": "wake_word_detected"})
        assert session.manager.wake_word_active is True

    @pytest.mark.asyncio
    async def test_check_wake_word_not_detected(self, session):
        """Test wake word not detected."""
        session.manager.wake_word_phrase = "hey computer"
        session._send_to_frontend = AsyncMock()

        await session._check_wake_word("What's the weather?")

        session._send_to_frontend.assert_not_called()

    async def test_send_to_frontend(self, session):
        """Test sending messages to frontend."""
        session.manager._broadcast_to_frontend = AsyncMock()

        message = {"type": "test"}

        await session._send_to_frontend(message)

        session.manager._broadcast_to_frontend.assert_called_once_with(
            session.conversation_id, message
        )


class TestGlobalConversationManager:
    """Test the global conversation manager instance."""

    def test_global_instance_exists(self):
        """Test that global conversation manager instance exists."""
        assert isinstance(conversation_manager, ConversationManager)
        assert hasattr(conversation_manager, "start_conversation")
        assert hasattr(conversation_manager, "end_conversation")


class TestIntegration:
    """Integration tests for conversation manager."""

    @pytest.mark.asyncio
    @patch("talk2me_ui.conversation_manager.websockets.connect")
    async def test_full_conversation_flow(self, mock_ws_connect):
        """Test a full conversation flow."""
        manager = ConversationManager()

        # Mock backend WebSocket
        mock_backend_ws = AsyncMock()
        mock_ws_connect.return_value = mock_backend_ws

        # Start conversation
        frontend_ws = AsyncMock()
        conversation_id = await manager.start_conversation(frontend_ws)

        assert conversation_id in manager.active_conversations

        # Send a message
        message = json.dumps({"type": "start_recording"})
        await manager.handle_frontend_message(conversation_id, frontend_ws, message)

        # End conversation
        await manager.end_conversation(conversation_id)

        assert conversation_id not in manager.active_conversations
