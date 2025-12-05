"""
API client for Talk2Me backend communication.

This module provides a client class for interacting with the Talk2Me backend API,
including methods for speech-to-text, text-to-speech, voice management, and media
resource handling.
"""

import logging
from typing import Any, BinaryIO
from urllib.parse import urljoin

import requests

from .config import get_config

logger = logging.getLogger("talk2me_ui.api_client")


class Talk2MeAPIClient:
    """
    Client for interacting with the Talk2Me backend API.

    Provides methods for all backend endpoints with proper error handling,
    response parsing, and file upload support.
    """

    def __init__(self, base_url: str | None = None):
        """
        Initialize the API client.

        Args:
            base_url: Base URL for the backend API. If None, uses config.
        """
        if base_url is None:
            config = get_config()
            base_url = str(config.backend.url)

        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        logger.info("API client initialized", extra={"base_url": self.base_url})

    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """
        Make an HTTP request to the backend API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            **kwargs: Additional arguments for requests

        Returns:
            Response object

        Raises:
            requests.RequestException: For network/connection errors
            ValueError: For invalid responses
        """
        url = urljoin(self.base_url + "/", endpoint.lstrip("/"))

        logger.debug(
            "Making API request", extra={"method": method, "url": url, "endpoint": endpoint}
        )

        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            logger.debug(
                "API request successful",
                extra={
                    "method": method,
                    "url": url,
                    "status_code": response.status_code,
                    "response_size": len(response.content) if response.content else 0,
                },
            )
            return response
        except requests.RequestException as e:
            logger.error(
                "API request failed",
                extra={"method": method, "url": url, "error": str(e)},
                exc_info=True,
            )
            raise requests.RequestException(f"API request failed: {e}") from e

    def _parse_json_response(self, response: requests.Response) -> Any:
        """
        Parse JSON response from the API.

        Args:
            response: Response object

        Returns:
            Parsed JSON data

        Raises:
            ValueError: If response is not valid JSON
        """
        try:
            return response.json()
        except ValueError as e:
            raise ValueError(f"Invalid JSON response: {e}") from e

    def health_check(self) -> dict[str, Any]:
        """
        Check the health status of the backend API.

        Returns:
            Health check response data

        Raises:
            requests.RequestException: For network errors
            ValueError: For invalid responses
        """
        response = self._make_request("GET", "/")
        return self._parse_json_response(response)

    def stt_transcribe(
        self, audio_file: BinaryIO, sample_rate: int | None = None
    ) -> dict[str, Any]:
        """
        Transcribe speech from an audio file.

        Args:
            audio_file: Binary file-like object containing audio data
            sample_rate: Optional sample rate override

        Returns:
            Transcription response with 'text' field

        Raises:
            requests.RequestException: For network errors
            ValueError: For invalid responses
        """
        logger.info("Starting STT transcription", extra={"sample_rate": sample_rate})
        files = {"file": audio_file}
        params = {}
        if sample_rate is not None:
            params["sample_rate"] = sample_rate

        response = self._make_request("POST", "/stt", files=files, params=params)
        result = self._parse_json_response(response)
        logger.info(
            "STT transcription completed", extra={"text_length": len(result.get("text", ""))}
        )
        return result

    def tts_synthesize(self, text: str, voice: str, **kwargs) -> bytes:
        """
        Synthesize speech from text using a specific voice.

        Args:
            text: Text to synthesize
            voice: Voice identifier to use
            **kwargs: Additional parameters (speed, pitch, output_format, etc.)

        Returns:
            Audio data as bytes

        Raises:
            requests.RequestException: For network errors
            ValueError: For invalid parameters or responses
        """
        if not text.strip():
            raise ValueError("Text cannot be empty")

        logger.info(
            "Starting TTS synthesis",
            extra={"voice": voice, "text_length": len(text), "kwargs": kwargs},
        )
        data = {"text": text, "voice": voice, **kwargs}
        response = self._make_request("POST", "/tts", json=data)

        # Return raw audio bytes
        audio_data = response.content
        logger.info(
            "TTS synthesis completed", extra={"voice": voice, "audio_size": len(audio_data)}
        )
        return audio_data

    def tts_synthesize_async(self, text: str, voice: str, **kwargs) -> dict[str, Any]:
        """
        Start asynchronous speech synthesis from text.

        Args:
            text: Text to synthesize
            voice: Voice identifier to use
            **kwargs: Additional parameters (speed, pitch, output_format, etc.)

        Returns:
            Task response with task_id

        Raises:
            requests.RequestException: For network errors
            ValueError: For invalid parameters or responses
        """
        if not text.strip():
            raise ValueError("Text cannot be empty")

        data = {"text": text, "voice": voice, **kwargs}
        response = self._make_request("POST", "/tts/async", json=data)
        return self._parse_json_response(response)

    def tts_get_status(self, task_id: str) -> dict[str, Any]:
        """
        Get the status of an asynchronous TTS task.

        Args:
            task_id: Task identifier

        Returns:
            Task status response

        Raises:
            requests.RequestException: For network errors
            ValueError: For invalid responses
        """
        response = self._make_request("GET", f"/tts/status/{task_id}")
        return self._parse_json_response(response)

    def list_voices(self) -> dict[str, Any]:
        """
        List all available voices.

        Returns:
            Response containing list of voices

        Raises:
            requests.RequestException: For network errors
            ValueError: For invalid responses
        """
        response = self._make_request("GET", "/voices")
        return self._parse_json_response(response)

    def create_voice(
        self, name: str, language: str = "en", samples: list[BinaryIO] | None = None
    ) -> dict[str, Any]:
        """
        Create a new voice profile.

        Args:
            name: Display name for the voice
            language: Language code (default: 'en')
            samples: Optional list of audio sample files

        Returns:
            Voice creation response

        Raises:
            requests.RequestException: For network errors
            ValueError: For invalid parameters or responses
        """
        if not name.strip():
            raise ValueError("Voice name cannot be empty")

        data = {"name": name, "language": language}
        files = {}

        if samples:
            for _i, sample in enumerate(samples):
                files["samples"] = sample  # FastAPI expects multiple files with same key

        response = self._make_request("POST", "/voices", data=data, files=files)
        return self._parse_json_response(response)

    def update_voice(
        self, voice_id: str, name: str | None = None, language: str | None = None
    ) -> dict[str, Any]:
        """
        Update a voice profile.

        Args:
            voice_id: Identifier of the voice to update
            name: New display name (optional)
            language: New language code (optional)

        Returns:
            Update confirmation response

        Raises:
            requests.RequestException: For network errors
            ValueError: For invalid parameters or responses
        """
        if not voice_id.strip():
            raise ValueError("Voice ID cannot be empty")

        data = {}
        if name is not None:
            data["name"] = name
        if language is not None:
            data["language"] = language

        if not data:
            raise ValueError("At least one field must be provided for update")

        response = self._make_request("PUT", f"/voices/{voice_id}", json=data)
        return self._parse_json_response(response)

    def delete_voice(self, voice_id: str) -> dict[str, Any]:
        """
        Delete a voice profile.

        Args:
            voice_id: Identifier of the voice to delete

        Returns:
            Deletion confirmation response

        Raises:
            requests.RequestException: For network errors
            ValueError: For invalid parameters or responses
        """
        if not voice_id.strip():
            raise ValueError("Voice ID cannot be empty")

        response = self._make_request("DELETE", f"/voices/{voice_id}")
        return self._parse_json_response(response)

    def clone_voice(self, voice_id: str, samples: list[BinaryIO]) -> dict[str, Any]:
        """
        Clone an existing voice by adding new samples.

        Args:
            voice_id: Identifier of the voice to clone/extend
            samples: List of audio sample files to add

        Returns:
            Clone operation response

        Raises:
            requests.RequestException: For network errors
            ValueError: For invalid parameters or responses
        """
        if not voice_id.strip():
            raise ValueError("Voice ID cannot be empty")
        if not samples:
            raise ValueError("At least one sample file is required")

        files = {}
        for _i, sample in enumerate(samples):
            files["samples"] = sample

        response = self._make_request("POST", f"/voices/{voice_id}/samples", files=files)
        return self._parse_json_response(response)

    def generate_audiobook(self, text: str, voice: str, **kwargs) -> bytes:
        """
        Generate an audiobook from text.

        Args:
            text: Full text content for the audiobook
            voice: Voice to use for narration
            **kwargs: Additional parameters (format, speed, etc.)

        Returns:
            Audiobook audio data as bytes

        Raises:
            requests.RequestException: For network errors
            ValueError: For invalid parameters
        """
        if not text.strip():
            raise ValueError("Text cannot be empty")

        data = {"text": text, "voice": voice, **kwargs}
        response = self._make_request("POST", "/audiobook", json=data)

        return response.content

    def list_sound_effects(self) -> dict[str, Any]:
        """
        List all available sound effects.

        Returns:
            Response containing list of sound effects

        Raises:
            requests.RequestException: For network errors
            ValueError: For invalid responses
        """
        response = self._make_request("GET", "/sound-effects")
        return self._parse_json_response(response)

    def upload_sound_effect(self, name: str, audio_file: BinaryIO, **metadata) -> dict[str, Any]:
        """
        Upload a new sound effect.

        Args:
            name: Name/identifier for the sound effect
            audio_file: Audio file to upload
            **metadata: Additional metadata fields

        Returns:
            Upload confirmation response

        Raises:
            requests.RequestException: For network errors
            ValueError: For invalid parameters or responses
        """
        if not name.strip():
            raise ValueError("Sound effect name cannot be empty")

        data = {"name": name, **metadata}
        files = {"file": audio_file}

        response = self._make_request("POST", "/sound-effects", data=data, files=files)
        return self._parse_json_response(response)

    def list_background_audio(self) -> dict[str, Any]:
        """
        List all available background audio tracks.

        Returns:
            Response containing list of background audio

        Raises:
            requests.RequestException: For network errors
            ValueError: For invalid responses
        """
        response = self._make_request("GET", "/background-audio")
        return self._parse_json_response(response)

    def upload_background_audio(
        self, name: str, audio_file: BinaryIO, **metadata
    ) -> dict[str, Any]:
        """
        Upload a new background audio track.

        Args:
            name: Name/identifier for the background audio
            audio_file: Audio file to upload
            **metadata: Additional metadata fields

        Returns:
            Upload confirmation response

        Raises:
            requests.RequestException: For network errors
            ValueError: For invalid parameters or responses
        """
        if not name.strip():
            raise ValueError("Background audio name cannot be empty")

        data = {"name": name, **metadata}
        files = {"file": audio_file}

        response = self._make_request("POST", "/background-audio", data=data, files=files)
        return self._parse_json_response(response)
