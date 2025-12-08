"""Conversation manager for real-time WebSocket communication.

This module handles the coordination between frontend WebSocket connections
and the Talk2Me backend WebSocket for real-time audio streaming, STT/TTS processing,
and wake word detection.
"""

import asyncio
import json
import logging
import uuid
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosedError

from .api_client import Talk2MeAPIClient
from .config import get_config

logger = logging.getLogger("talk2me_ui.conversation_manager")


class ConversationManager:
    """Manages real-time conversations via WebSocket connections.

    Coordinates between frontend clients and the Talk2Me backend WebSocket
    for bidirectional audio streaming and real-time processing.
    """

    def __init__(self, backend_url: str | None = None):
        """Initialize the conversation manager.

        Args:
            backend_url: URL of the Talk2Me backend WebSocket endpoint
        """
        if backend_url is None:
            config = get_config()
            # Assume backend WebSocket is at /ws on the same host as the API
            backend_base = str(config.backend.url)
            self.backend_url = backend_base.replace("http", "ws") + "/ws"
        else:
            self.backend_url = backend_url

        self.api_client = Talk2MeAPIClient()

        # Active conversations: conversation_id -> ConversationSession
        self.active_conversations: dict[str, ConversationSession] = {}

        # Frontend connections: conversation_id -> set of WebSocket connections
        self.frontend_connections: dict[str, set[websockets.WebSocketServerProtocol]] = {}

        # Wake word detection state
        self.wake_word_active = False
        self.wake_word_phrase = "hey talk2me"  # Configurable

        logger.info("Conversation manager initialized", extra={"backend_url": self.backend_url})

    async def start_conversation(self, websocket: websockets.WebSocketServerProtocol) -> str:
        """Start a new conversation session.

        Args:
            websocket: Frontend WebSocket connection

        Returns:
            Conversation ID
        """
        conversation_id = str(uuid.uuid4())

        # Create conversation session
        session = ConversationSession(conversation_id, self.backend_url, self)
        self.active_conversations[conversation_id] = session

        # Add frontend connection
        if conversation_id not in self.frontend_connections:
            self.frontend_connections[conversation_id] = set()
        self.frontend_connections[conversation_id].add(websocket)

        # Start the session
        asyncio.create_task(session.start())

        logger.info(
            "Started conversation",
            extra={
                "conversation_id": conversation_id,
                "active_conversations": len(self.active_conversations),
            },
        )
        return conversation_id

    async def end_conversation(self, conversation_id: str):
        """End a conversation session.

        Args:
            conversation_id: ID of the conversation to end
        """
        if conversation_id in self.active_conversations:
            session = self.active_conversations[conversation_id]
            await session.stop()
            del self.active_conversations[conversation_id]

        if conversation_id in self.frontend_connections:
            # Close all frontend connections for this conversation
            for ws in self.frontend_connections[conversation_id]:
                try:
                    await ws.close()
                except Exception as e:
                    logger.error(f"Error closing frontend connection: {e}")
            del self.frontend_connections[conversation_id]

        logger.info(f"Ended conversation {conversation_id}")

    async def handle_frontend_message(
        self, conversation_id: str, _websocket: websockets.WebSocketServerProtocol, message: str
    ):
        """Handle a message from a frontend client.

        Args:
            conversation_id: ID of the conversation
            _websocket: Frontend WebSocket connection
            message: Message data
        """
        try:
            data = json.loads(message)
            message_type = data.get("type")

            if message_type == "audio_data":
                await self._handle_audio_data(conversation_id, data)
            elif message_type == "start_recording":
                await self._handle_start_recording(conversation_id)
            elif message_type == "stop_recording":
                await self._handle_stop_recording(conversation_id)
            elif message_type == "wake_word_detected":
                await self._handle_wake_word_detected(conversation_id)
            else:
                logger.warning(f"Unknown message type: {message_type}")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON message: {e}")
        except Exception as e:
            logger.error(f"Error handling frontend message: {e}")

    async def _handle_audio_data(self, conversation_id: str, data: dict[str, Any]):
        """Handle incoming audio data from frontend."""
        if conversation_id in self.active_conversations:
            session = self.active_conversations[conversation_id]
            await session.send_audio_to_backend(data.get("audio", b""))

    async def _handle_start_recording(self, conversation_id: str):
        """Handle start recording command."""
        if conversation_id in self.active_conversations:
            session = self.active_conversations[conversation_id]
            session.recording_active = True
            await self._broadcast_to_frontend(conversation_id, {"type": "recording_started"})

    async def _handle_stop_recording(self, conversation_id: str):
        """Handle stop recording command."""
        if conversation_id in self.active_conversations:
            session = self.active_conversations[conversation_id]
            session.recording_active = False
            await self._broadcast_to_frontend(conversation_id, {"type": "recording_stopped"})

    async def _handle_wake_word_detected(self, conversation_id: str):
        """Handle wake word detection."""
        self.wake_word_active = True
        await self._broadcast_to_frontend(conversation_id, {"type": "wake_word_activated"})

    async def _broadcast_to_frontend(self, conversation_id: str, message: dict[str, Any]):
        """Broadcast a message to all frontend connections for a conversation."""
        if conversation_id in self.frontend_connections:
            message_json = json.dumps(message)
            for ws in self.frontend_connections[conversation_id]:
                try:
                    await ws.send(message_json)
                except Exception as e:
                    logger.error(f"Error sending message to frontend: {e}")

    async def remove_frontend_connection(
        self, conversation_id: str, websocket: websockets.WebSocketServerProtocol
    ):
        """Remove a frontend connection from a conversation."""
        if conversation_id in self.frontend_connections:
            self.frontend_connections[conversation_id].discard(websocket)
            if not self.frontend_connections[conversation_id]:
                # No more connections, end the conversation
                await self.end_conversation(conversation_id)


class ConversationSession:
    """Represents a single conversation session with the backend."""

    def __init__(
        self, conversation_id: str, backend_url: str | None, manager: "ConversationManager"
    ):
        """Initialize a conversation session.

        Args:
            conversation_id: Unique conversation identifier
            backend_url: Backend WebSocket URL
            manager: Reference to the conversation manager
        """
        self.conversation_id = conversation_id
        self.backend_url = backend_url
        self.manager = manager
        self.backend_ws: websockets.WebSocketServerProtocol | None = None
        self.recording_active = False
        self.is_active = False

    async def start(self):
        """Start the conversation session."""
        self.is_active = True

        if self.backend_url:
            try:
                self.backend_ws = await websockets.connect(self.backend_url)
                asyncio.create_task(self._listen_to_backend())
                logger.info(f"Connected to backend for conversation {self.conversation_id}")
            except Exception as e:
                logger.error(f"Failed to connect to backend: {e}")

    async def stop(self):
        """Stop the conversation session."""
        self.is_active = False

        if self.backend_ws:
            try:
                await self.backend_ws.close()
            except Exception as e:
                logger.error(f"Error closing backend connection: {e}")

    async def send_audio_to_backend(self, audio_data: bytes):
        """Send audio data to the backend."""
        if self.backend_ws and self.recording_active:
            try:
                # Send audio data to backend
                await self.backend_ws.send(audio_data)
            except Exception as e:
                logger.error(f"Error sending audio to backend: {e}")

    async def _listen_to_backend(self):
        """Listen for messages from the backend."""
        try:
            while self.is_active and self.backend_ws:
                try:
                    message = await self.backend_ws.recv()
                    await self._handle_backend_message(message)
                except ConnectionClosedError:
                    logger.info(
                        f"Backend connection closed for conversation {self.conversation_id}"
                    )
                    break
                except Exception as e:
                    logger.error(f"Error receiving from backend: {e}")
                    break
        except Exception as e:
            logger.error(f"Backend listener error: {e}")
        finally:
            self.backend_ws = None

    async def _handle_backend_message(self, message: str):
        """Handle a message from the backend."""
        try:
            if isinstance(message, str):
                data = json.loads(message)
            else:
                # Binary message (likely audio)
                data = {"type": "audio_response", "audio": message}

            # Process different message types
            message_type = data.get("type")

            if message_type == "transcription":
                # Forward transcription to frontend
                text = data.get("text", "")
                await self._send_to_frontend(
                    {
                        "type": "transcription",
                        "text": text,
                        "confidence": data.get("confidence", 0.0),
                    }
                )

                # Check for wake word
                await self._check_wake_word(text)

            elif message_type == "tts_audio":
                # Forward TTS audio to frontend
                await self._send_to_frontend({"type": "tts_audio", "audio": data.get("audio", b"")})
            elif message_type == "wake_word_detected":
                # Handle wake word detection
                await self._send_to_frontend({"type": "wake_word_detected"})

        except json.JSONDecodeError:
            # Handle binary audio data
            await self._send_to_frontend({"type": "audio_response", "audio": message})
        except Exception as e:
            logger.error(f"Error handling backend message: {e}")

    async def _check_wake_word(self, text: str):
        """Check if the transcribed text contains the wake word."""
        wake_word = self.manager.wake_word_phrase.lower()
        if wake_word and wake_word in text.lower():
            self.manager.wake_word_active = True
            await self._send_to_frontend({"type": "wake_word_detected"})

    async def _send_to_frontend(self, message: dict[str, Any]):
        """Send a message to the frontend (via conversation manager)."""
        await self.manager._broadcast_to_frontend(self.conversation_id, message)


# Global conversation manager instance
conversation_manager = ConversationManager()
