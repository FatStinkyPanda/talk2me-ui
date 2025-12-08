"""Tests for file handling functionality."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from src.talk2me_ui.file_handler import (
    ChunkedAudioProcessor,
    StreamingFileHandler,
    get_audio_processor,
    get_streaming_handler,
)


class TestStreamingFileHandler:
    """Test cases for StreamingFileHandler class."""

    def test_initialization(self):
        """Test StreamingFileHandler initialization."""
        handler = StreamingFileHandler(chunk_size=1024, max_file_size=1024 * 1024)
        assert handler.chunk_size == 1024
        assert handler.max_file_size == 1024 * 1024

    def test_create_temp_file(self):
        """Test temporary file creation."""
        handler = StreamingFileHandler()
        temp_path = handler.create_temp_file(".test")

        assert temp_path.exists()
        assert temp_path.suffix == ".test"

        # Clean up
        temp_path.unlink()

    def test_cleanup_temp_file(self):
        """Test temporary file cleanup."""
        handler = StreamingFileHandler()

        # Create a temp file
        temp_path = handler.create_temp_file()
        assert temp_path.exists()

        # Clean it up
        handler.cleanup_temp_file(temp_path)
        assert not temp_path.exists()

    @pytest.mark.asyncio
    async def test_validate_and_save_file_success(self):
        """Test successful file validation and saving."""
        handler = StreamingFileHandler(max_file_size=1024, chunk_size=10)

        # Create a mock upload file that returns data in chunks
        mock_file = Mock()
        mock_file.content_type = "audio/wav"
        # Return data in chunks, then empty bytes to end
        mock_file.read = AsyncMock(side_effect=[b"test audio ", b"data", b""])

        destination = Path(tempfile.mktemp())

        try:
            saved_path = await handler.validate_and_save_file(mock_file, destination, {"audio/wav"})

            assert saved_path == destination
            assert destination.exists()
            assert destination.read_bytes() == b"test audio data"

        finally:
            if destination.exists():
                destination.unlink()

    @pytest.mark.asyncio
    async def test_validate_and_save_file_invalid_type(self):
        """Test file validation with invalid type."""
        handler = StreamingFileHandler()

        mock_file = Mock()
        mock_file.content_type = "text/plain"

        destination = Path(tempfile.mktemp())

        with pytest.raises(Exception):  # Should raise HTTPException
            await handler.validate_and_save_file(mock_file, destination, {"audio/wav"})

    @pytest.mark.asyncio
    async def test_validate_and_save_file_too_large(self):
        """Test file validation with file too large."""
        handler = StreamingFileHandler(max_file_size=10)

        mock_file = Mock()
        mock_file.content_type = "audio/wav"
        mock_file.read = AsyncMock(return_value=b"this is too long")

        destination = Path(tempfile.mktemp())

        with pytest.raises(Exception):  # Should raise HTTPException
            await handler.validate_and_save_file(mock_file, destination, {"audio/wav"})

    @pytest.mark.asyncio
    async def test_process_file_in_chunks(self):
        """Test chunked file processing."""
        handler = StreamingFileHandler()

        # Create a test file
        test_data = b"0123456789" * 10  # 100 bytes
        temp_file = Path(tempfile.mktemp())
        temp_file.write_bytes(test_data)

        try:
            chunks = []

            async def async_processor(chunk):
                return [chunk]

            async for chunk in handler.process_file_in_chunks(
                temp_file, async_processor, chunk_size=10
            ):
                chunks.extend(chunk)

            # Should have processed in chunks
            assert len(chunks) > 1
            assert b"".join(chunks) == test_data

        finally:
            temp_file.unlink()


class TestChunkedAudioProcessor:
    """Test cases for ChunkedAudioProcessor class."""

    def test_initialization(self):
        """Test ChunkedAudioProcessor initialization."""
        processor = ChunkedAudioProcessor(chunk_size=512)
        assert processor.chunk_size == 512

    @pytest.mark.asyncio
    async def test_process_audio_stream(self):
        """Test audio stream processing."""
        processor = ChunkedAudioProcessor(chunk_size=10)

        # Create test audio data that will be processed in chunks
        # Total data: b'chunk1_longerchunk2_longerchunk3_longer' (39 bytes)
        # With chunk_size=10, it will process in chunks of 10 bytes
        audio_chunks = [b"chunk1_longer", b"chunk2_longer", b"chunk3_longer"]

        async def audio_generator():
            for chunk in audio_chunks:
                yield chunk

        processed_chunks = []
        async for chunk in processor.process_audio_stream(audio_generator()):
            processed_chunks.append(chunk)

        # The processor accumulates data and yields chunks of chunk_size
        # Input: 13 + 13 + 13 = 39 bytes
        # Output: 10 + 10 + 10 + 9 = 39 bytes (3 full chunks + remainder)
        assert len(processed_chunks) == 4  # 3 chunks of 10 bytes + 1 remainder chunk
        assert sum(len(chunk) for chunk in processed_chunks) == 39  # Total bytes preserved


class TestGlobalInstances:
    """Test global instance functions."""

    def test_get_streaming_handler(self):
        """Test getting streaming handler instance."""
        handler = get_streaming_handler()
        assert isinstance(handler, StreamingFileHandler)

    def test_get_audio_processor(self):
        """Test getting audio processor instance."""
        processor = get_audio_processor()
        assert isinstance(processor, ChunkedAudioProcessor)

    def test_singleton_behavior(self):
        """Test that global instances are singletons."""
        handler1 = get_streaming_handler()
        handler2 = get_streaming_handler()
        assert handler1 is handler2

        processor1 = get_audio_processor()
        processor2 = get_audio_processor()
        assert processor1 is processor2
