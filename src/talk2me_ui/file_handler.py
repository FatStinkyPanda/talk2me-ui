"""Large file handling utilities for Talk2Me UI.

This module provides streaming file upload, chunked processing,
and memory-efficient file operations for large audio files.
"""

import hashlib
import io
import logging
import os
import tempfile
from pathlib import Path
from typing import AsyncGenerator, BinaryIO, Optional

import aiofiles
from fastapi import HTTPException, UploadFile

logger = logging.getLogger(__name__)


class StreamingFileHandler:
    """Handles large file uploads with streaming and chunked processing."""

    def __init__(self, chunk_size: int = 8192, max_file_size: int = 50 * 1024 * 1024):
        self.chunk_size = chunk_size
        self.max_file_size = max_file_size

    async def validate_and_save_file(
        self,
        file: UploadFile,
        destination: Path,
        allowed_types: Optional[set[str]] = None
    ) -> Path:
        """Validate and save an uploaded file with streaming.

        Args:
            file: The uploaded file
            destination: Destination directory
            allowed_types: Set of allowed MIME types

        Returns:
            Path to the saved file

        Raises:
            HTTPException: If validation fails
        """
        # Validate file type
        if allowed_types and file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type: {file.content_type}. Allowed: {', '.join(allowed_types)}"
            )

        # Create destination directory
        destination.parent.mkdir(parents=True, exist_ok=True)

        # Stream file to disk with size validation
        total_size = 0
        hasher = hashlib.sha256()

        try:
            async with aiofiles.open(destination, 'wb') as f:
                while chunk := await file.read(self.chunk_size):
                    total_size += len(chunk)

                    # Check file size limit
                    if total_size > self.max_file_size:
                        await f.close()
                        destination.unlink(missing_ok=True)
                        raise HTTPException(
                            status_code=413,
                            detail=f"File too large. Maximum size: {self.max_file_size} bytes"
                        )

                    await f.write(chunk)
                    hasher.update(chunk)

        except Exception as e:
            # Clean up partial file
            destination.unlink(missing_ok=True)
            logger.error(f"File upload failed: {e}")
            raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")

        # Validate file was written completely
        if total_size == 0:
            destination.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail="Empty file")

        file_hash = hasher.hexdigest()
        logger.info(
            f"File saved successfully: {destination.name}, "
            f"size={total_size}, hash={file_hash[:8]}..."
        )

        return destination

    async def process_file_in_chunks(
        self,
        file_path: Path,
        processor_func,
        chunk_size: Optional[int] = None
    ) -> AsyncGenerator[bytes, None]:
        """Process a file in chunks to avoid loading it entirely into memory.

        Args:
            file_path: Path to the file to process
            processor_func: Function to process each chunk
            chunk_size: Size of chunks to read

        Yields:
            Processed chunks
        """
        chunk_size = chunk_size or self.chunk_size

        try:
            async with aiofiles.open(file_path, 'rb') as f:
                while chunk := await f.read(chunk_size):
                    processed_chunk = await processor_func(chunk)
                    if processed_chunk:
                        yield processed_chunk

        except Exception as e:
            logger.error(f"Chunked file processing failed: {e}")
            raise

    def create_temp_file(self, suffix: str = "") -> Path:
        """Create a temporary file with optional suffix.

        Args:
            suffix: File suffix (e.g., '.wav', '.tmp')

        Returns:
            Path to temporary file
        """
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)  # Close the file descriptor, keep the path
        return Path(path)

    def cleanup_temp_file(self, file_path: Path) -> None:
        """Safely remove a temporary file.

        Args:
            file_path: Path to the file to remove
        """
        try:
            if file_path.exists():
                file_path.unlink()
                logger.debug(f"Cleaned up temporary file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temporary file {file_path}: {e}")


class ChunkedAudioProcessor:
    """Processes large audio files in chunks to minimize memory usage."""

    def __init__(self, chunk_size: int = 4096):
        self.chunk_size = chunk_size

    async def process_audio_stream(
        self,
        audio_data: AsyncGenerator[bytes, None],
        sample_rate: int = 22050
    ) -> AsyncGenerator[bytes, None]:
        """Process audio data stream with memory-efficient operations.

        Args:
            audio_data: Stream of audio data chunks
            sample_rate: Target sample rate

        Yields:
            Processed audio chunks
        """
        # This is a placeholder for actual audio processing
        # In a real implementation, you would use libraries like pydub
        # or ffmpeg-python for streaming audio processing

        buffer = bytearray()

        async for chunk in audio_data:
            buffer.extend(chunk)

            # Process when buffer reaches a certain size
            if len(buffer) >= self.chunk_size:
                # Process the chunk (placeholder logic)
                processed_chunk = self._process_audio_chunk(bytes(buffer[:self.chunk_size]))

                # Keep remainder in buffer
                buffer = buffer[self.chunk_size:]

                if processed_chunk:
                    yield processed_chunk

        # Process remaining buffer
        if buffer:
            processed_chunk = self._process_audio_chunk(bytes(buffer))
            if processed_chunk:
                yield processed_chunk

    def _process_audio_chunk(self, chunk: bytes) -> bytes:
        """Process a single audio chunk.

        Args:
            chunk: Raw audio chunk

        Returns:
            Processed audio chunk
        """
        # Placeholder processing - in real implementation this would
        # apply audio effects, normalization, etc.
        return chunk


# Global instances
streaming_handler = StreamingFileHandler()
audio_processor = ChunkedAudioProcessor()


def get_streaming_handler() -> StreamingFileHandler:
    """Get the global streaming file handler instance."""
    return streaming_handler


def get_audio_processor() -> ChunkedAudioProcessor:
    """Get the global audio processor instance."""
    return audio_processor
