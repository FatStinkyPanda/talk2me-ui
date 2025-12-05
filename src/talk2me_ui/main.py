"""
Main FastAPI application for Talk2Me UI.

This module sets up the FastAPI application with Jinja2 templates,
static file serving, CORS middleware, and route handlers for all
main sections of the application.
"""

import io
import json
import logging
import logging.config
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .api_client import Talk2MeAPIClient
from .conversation_manager import conversation_manager
from .exceptions import (
    ExternalServiceError,
    NotFoundError,
    Talk2MeException,
    ValidationError,
    handle_exception,
)
from .markup_parser import parse_audiobook_markup, validate_audiobook_markup
from .validation import (
    InputSanitizer,
    validate_text_input,
    validation_middleware,
)


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields from record
        if hasattr(record, "extra_fields"):
            log_entry.update(record.extra_fields)

        return json.dumps(log_entry)


def setup_logging(log_level: str = "INFO", log_file: str | None = None) -> None:
    """
    Set up structured logging configuration.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path
    """
    # Convert string log level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Base configuration
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": JSONFormatter,
            },
            "console": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "console",
                "stream": sys.stdout,
                "level": numeric_level,
            },
        },
        "root": {
            "level": numeric_level,
            "handlers": ["console"],
        },
        "loggers": {
            "talk2me_ui": {
                "level": numeric_level,
                "handlers": ["console"],
                "propagate": False,
            },
            "uvicorn": {
                "level": "WARNING",  # Reduce uvicorn noise
                "handlers": ["console"],
                "propagate": False,
            },
            "websockets": {
                "level": "WARNING",  # Reduce websocket noise
                "handlers": ["console"],
                "propagate": False,
            },
        },
    }

    # Add file handler if log_file is specified
    if log_file:
        config["handlers"]["file"] = {
            "class": "logging.FileHandler",
            "formatter": "json",
            "filename": log_file,
            "level": numeric_level,
        }
        config["root"]["handlers"].append("file")
        config["loggers"]["talk2me_ui"]["handlers"].append("file")

    logging.config.dictConfig(config)


# Set up logging
setup_logging()

# Create FastAPI app instance
app = FastAPI(
    title="Talk2Me UI",
    description="Web interface for Talk2Me speech processing services",
    version="1.0.0",
)

# Configure Jinja2 templates
templates = Jinja2Templates(directory="src/talk2me_ui/templates")

# Mount static files
app.mount("/static", StaticFiles(directory="src/talk2me_ui/static"), name="static")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Add validation middleware
@app.middleware("http")
async def validation_middleware_handler(request: Request, call_next):
    """Middleware for request validation and security checks."""
    try:
        await validation_middleware.validate_request(request)
    except Talk2MeException as e:
        logger.warning(
            "Request validation failed",
            extra={
                "path": str(request.url.path),
                "method": request.method,
                "client_ip": request.client.host if request.client else "unknown",
                "error": e.error_code,
                "message": e.message,
            },
        )
        raise e

    response = await call_next(request)
    return response


# Initialize API client
api_client = Talk2MeAPIClient()

# Set up logging with contextual information
logger = logging.getLogger("talk2me_ui.main")

# Global dictionaries to track tasks
stt_tasks = {}
tts_tasks = {}
audiobook_tasks = {}

# Sound directories
SFX_DIR = Path("data/sfx")
BACKGROUND_DIR = Path("data/background")

# Ensure directories exist
SFX_DIR.mkdir(parents=True, exist_ok=True)
BACKGROUND_DIR.mkdir(parents=True, exist_ok=True)

# Audio validation constants
ALLOWED_AUDIO_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/wave",
    "audio/ogg",
    "audio/flac",
    "audio/aac",
    "audio/m4a",
}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


async def process_stt(task_id: str, tmp_path: str, sample_rate: int = None):
    """
    Background task to process STT transcription.

    Args:
        task_id: Unique task identifier
        tmp_path: Path to temporary audio file
        sample_rate: Optional sample rate override
    """
    logger.info(
        "Starting STT transcription", extra={"task_id": task_id, "sample_rate": sample_rate}
    )
    try:
        with open(tmp_path, "rb") as f:
            result = api_client.stt_transcribe(f, sample_rate)
        stt_tasks[task_id] = {"status": "completed", "result": result}
        logger.info(
            "STT transcription completed",
            extra={"task_id": task_id, "text_length": len(result.get("text", ""))},
        )
    except Exception as e:
        logger.error(
            "STT transcription failed", extra={"task_id": task_id, "error": str(e)}, exc_info=True
        )
        stt_tasks[task_id] = {"status": "failed", "error": str(e)}
    finally:
        try:
            os.unlink(tmp_path)
            logger.debug(
                "Cleaned up temporary STT file", extra={"task_id": task_id, "tmp_path": tmp_path}
            )
        except OSError as e:
            logger.warning(
                "Failed to clean up temporary STT file",
                extra={"task_id": task_id, "tmp_path": tmp_path, "error": str(e)},
            )


async def process_tts(task_id: str, text: str, voice: str, **kwargs):
    """
    Background task to process TTS synthesis.

    Args:
        task_id: Unique task identifier
        text: Text to synthesize
        voice: Voice identifier
        **kwargs: Additional parameters
    """
    logger.info(
        "Starting TTS synthesis",
        extra={"task_id": task_id, "voice": voice, "text_length": len(text)},
    )
    try:
        # For now, use synchronous TTS. In production, this might be async
        audio_data = api_client.tts_synthesize(text, voice, **kwargs)

        # Save audio to temporary file and create URL
        import base64

        audio_b64 = base64.b64encode(audio_data).decode("utf-8")
        filename = f"tts_{task_id}.wav"

        tts_tasks[task_id] = {
            "status": "completed",
            "audio_data": audio_b64,
            "filename": filename,
            "text": text,
        }
        logger.info(
            "TTS synthesis completed", extra={"task_id": task_id, "audio_size": len(audio_data)}
        )
    except Exception as e:
        logger.error(
            "TTS synthesis failed",
            extra={"task_id": task_id, "voice": voice, "error": str(e)},
            exc_info=True,
        )
        tts_tasks[task_id] = {"status": "failed", "error": str(e)}


async def process_audiobook(task_id: str, markup_text: str, **kwargs):
    """
    Background task to process audiobook generation from markup.

    Args:
        task_id: Unique task identifier
        markup_text: Text with triple-brace markup
        **kwargs: Additional parameters
    """
    logger.info(
        "Starting audiobook generation",
        extra={"task_id": task_id, "markup_length": len(markup_text)},
    )
    try:
        # Parse the markup
        sections = parse_audiobook_markup(markup_text)
        logger.debug(
            "Parsed markup sections", extra={"task_id": task_id, "sections_count": len(sections)}
        )

        if not sections:
            raise ValueError("No valid sections found in markup")

        # Generate audio for each section
        from pydub import AudioSegment

        combined_audio = AudioSegment.empty()

        for i, section in enumerate(sections):
            if section.text.strip():
                # Generate TTS for this section
                if not section.voice:
                    raise ValueError(f"No voice specified for section: {section.text[:50]}...")

                logger.debug(
                    "Generating TTS for section",
                    extra={
                        "task_id": task_id,
                        "section": i,
                        "voice": section.voice,
                        "text_length": len(section.text),
                    },
                )
                audio_data = api_client.tts_synthesize(section.text, section.voice, **kwargs)
                segment = AudioSegment.from_wav(io.BytesIO(audio_data))
                combined_audio += segment

            # TODO: Add sound effects and background audio integration
            # For now, skip sfx and bg

        # Export combined audio
        buffer = io.BytesIO()
        combined_audio.export(buffer, format="wav")
        audio_data = buffer.getvalue()

        # Save as base64
        import base64

        audio_b64 = base64.b64encode(audio_data).decode("utf-8")
        filename = f"audiobook_{task_id}.wav"

        audiobook_tasks[task_id] = {
            "status": "completed",
            "audio_data": audio_b64,
            "filename": filename,
            "sections_count": len(sections),
            "markup_text": markup_text,
        }
        logger.info(
            "Audiobook generation completed",
            extra={
                "task_id": task_id,
                "sections_count": len(sections),
                "audio_size": len(audio_data),
            },
        )
    except Exception as e:
        logger.error(
            "Audiobook generation failed",
            extra={"task_id": task_id, "error": str(e)},
            exc_info=True,
        )
        audiobook_tasks[task_id] = {"status": "failed", "error": str(e)}


def validate_audio_file(file: UploadFile) -> None:
    """
    Validate uploaded audio file.

    Args:
        file: Uploaded file to validate

    Raises:
        ValidationError: If validation fails
    """
    if file.content_type not in ALLOWED_AUDIO_TYPES:
        raise ValidationError(
            f"Unsupported file type: {file.content_type}. Allowed types: {', '.join(ALLOWED_AUDIO_TYPES)}",
            field="file",
            details={
                "allowed_types": list(ALLOWED_AUDIO_TYPES),
                "provided_type": file.content_type,
            },
        )

    # Check file size
    file.file.seek(0, 2)  # Seek to end
    size = file.file.tell()
    file.file.seek(0)  # Reset to beginning

    if size > MAX_FILE_SIZE:
        raise ValidationError(
            f"File too large: {size} bytes. Maximum allowed: {MAX_FILE_SIZE} bytes",
            field="file",
            details={"file_size": size, "max_size": MAX_FILE_SIZE},
        )


def save_sound_file(directory: Path, file: UploadFile, metadata: dict) -> str:
    """
    Save uploaded sound file and its metadata.

    Args:
        directory: Directory to save in (SFX_DIR or BACKGROUND_DIR)
        file: Uploaded file
        metadata: Metadata dictionary

    Returns:
        User-provided ID of the sound
    """
    sound_id = metadata.get("id", str(uuid4()))
    file_ext = Path(file.filename).suffix.lower()

    # Save audio file
    audio_filename = f"{sound_id}{file_ext}"
    audio_path = directory / audio_filename

    logger.info(
        "Saving sound file",
        extra={
            "sound_id": sound_id,
            "directory": str(directory),
            "filename": audio_filename,
            "original_filename": file.filename,
            "content_type": file.content_type,
        },
    )

    with open(audio_path, "wb") as f:
        content = file.file.read()
        f.write(content)

    # Save metadata
    metadata.update(
        {
            "filename": audio_filename,
            "original_filename": file.filename,
            "content_type": file.content_type,
            "size": len(content),
            "uploaded_at": str(uuid4()),  # Using uuid for timestamp
        }
    )

    metadata_path = directory / f"{sound_id}.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    logger.info(
        "Sound file saved successfully",
        extra={
            "sound_id": sound_id,
            "audio_path": str(audio_path),
            "metadata_path": str(metadata_path),
            "file_size": len(content),
        },
    )

    return sound_id


def list_sounds(directory: Path) -> list[dict]:
    """
    List all sounds in a directory with their metadata.

    Args:
        directory: Directory to list from

    Returns:
        List of sound metadata dictionaries
    """
    sounds = []
    for json_file in directory.glob("*.json"):
        try:
            with open(json_file) as f:
                metadata = json.load(f)
                sounds.append(metadata)
        except (json.JSONDecodeError, FileNotFoundError):
            continue  # Skip corrupted metadata files

    return sounds


# Exception handler for API errors
@app.exception_handler(Talk2MeException)
async def talk2me_exception_handler(request: Request, exc: Talk2MeException):
    """
    Handle Talk2Me custom exceptions with proper HTTP responses.

    Returns JSON error response for API routes, HTML for web routes.
    """
    logger.error(
        "Talk2Me exception occurred",
        extra={
            "error_code": exc.error_code,
            "message": exc.message,
            "status_code": exc.status_code,
            "details": exc.details,
            "path": str(request.url.path),
            "method": request.method,
        },
        exc_info=True,
    )

    # Check if this is an API request
    if request.url.path.startswith("/api/"):
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.error_code, "message": exc.message, "details": exc.details},
        )
    else:
        # Return HTML error page for web routes
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "error": exc.message, "status_code": exc.status_code},
            status_code=exc.status_code,
        )


# Exception handler for general errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for unhandled errors.

    Returns appropriate error response based on request type.
    """
    logger.error(
        "Unhandled exception occurred",
        extra={
            "error_type": type(exc).__name__,
            "message": str(exc),
            "path": str(request.url.path),
            "method": request.method,
        },
        exc_info=True,
    )

    # Use the handle_exception utility for consistent error handling
    http_exc = handle_exception(exc)

    # Check if this is an API request
    if request.url.path.startswith("/api/"):
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=http_exc.status_code,
            content={"error": "Internal Server Error", "message": http_exc.detail},
        )
    else:
        # Return HTML error page for web routes
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "error": str(exc), "status_code": http_exc.status_code},
            status_code=http_exc.status_code,
        )


# Health check endpoint
@app.get("/api/health")
async def health_check():
    """
    Health check endpoint for monitoring and load balancers.

    Returns:
        Health status with basic system information
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "version": "1.0.0",
        "service": "talk2me-ui",
    }


# Route handlers


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard page."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/voices", response_class=HTMLResponse)
async def voice_management(request: Request):
    """Voice management page."""
    return templates.TemplateResponse("voices.html", {"request": request})


@app.get("/stt", response_class=HTMLResponse)
async def speech_to_text(request: Request):
    """Speech-to-text page."""
    return templates.TemplateResponse("stt.html", {"request": request})


@app.get("/tts", response_class=HTMLResponse)
async def text_to_speech(request: Request):
    """Text-to-speech page."""
    return templates.TemplateResponse("tts.html", {"request": request})


@app.get("/audiobook", response_class=HTMLResponse)
async def audiobook_studio(request: Request):
    """Audiobook studio page."""
    return templates.TemplateResponse("audiobook.html", {"request": request})


@app.get("/sounds", response_class=HTMLResponse)
async def sound_library(request: Request):
    """Sound library page."""
    return templates.TemplateResponse("sounds.html", {"request": request})


@app.post("/api/stt")
async def stt_upload(
    audio_file: UploadFile = File(...),
    sample_rate: int = Form(None),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """
    Upload audio file for speech-to-text transcription.

    Args:
        audio_file: Audio file to transcribe
        sample_rate: Optional sample rate override

    Returns:
        Task ID for tracking transcription progress
    """
    logger.info(
        "STT upload request received",
        extra={
            "filename": audio_file.filename,
            "content_type": audio_file.content_type,
            "sample_rate": sample_rate,
        },
    )

    # Validate the uploaded file
    validate_audio_file(audio_file)

    task_id = str(uuid4())

    try:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            content = await audio_file.read()
            tmp.write(content)
            tmp_path = tmp.name

        logger.info(
            "STT task created",
            extra={"task_id": task_id, "file_size": len(content), "tmp_path": tmp_path},
        )

        stt_tasks[task_id] = {"status": "processing", "result": None}
        background_tasks.add_task(process_stt, task_id, tmp_path, sample_rate)

        return {"task_id": task_id}
    except Exception as e:
        logger.error(
            "Failed to create STT task", extra={"task_id": task_id, "error": str(e)}, exc_info=True
        )
        raise ExternalServiceError("STT service", "Failed to process upload")


@app.get("/api/stt/{task_id}")
async def stt_status(task_id: str):
    """
    Get the status of an STT transcription task.

    Args:
        task_id: Task identifier

    Returns:
        Task status and result if completed
    """
    logger.debug("STT status request", extra={"task_id": task_id})

    if task_id not in stt_tasks:
        logger.warning("STT task not found", extra={"task_id": task_id})
        raise NotFoundError("STT task", task_id)

    task = stt_tasks[task_id]
    logger.debug(
        "STT task status retrieved", extra={"task_id": task_id, "status": task.get("status")}
    )

    return task


@app.get("/api/voices")
async def list_voices():
    """
    Get list of available voices.

    Returns:
        List of voice objects
    """
    try:
        voices = api_client.list_voices()
        return voices
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tts")
@validate_text_input(min_length=1, max_length=5000, disallow_html=True)
async def tts_generate(
    text: str = Form(...),
    voice_id: str = Form(...),
    speed: float = Form(1.0),
    pitch: int = Form(0),
    output_format: str = Form("wav"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """
    Generate speech from text using specified voice and parameters.

    Args:
        text: Text to synthesize
        voice_id: Voice identifier
        speed: Speech speed multiplier
        pitch: Pitch adjustment in semitones
        output_format: Output audio format

    Returns:
        Task ID for tracking synthesis progress
    """
    logger.info(
        "TTS generation request",
        extra={
            "text_length": len(text),
            "voice_id": voice_id,
            "speed": speed,
            "pitch": pitch,
            "output_format": output_format,
        },
    )

    # Sanitize inputs
    text = InputSanitizer.sanitize_text(text)
    voice_id = InputSanitizer.sanitize_text(voice_id)

    # Additional validation
    if not voice_id.strip():
        raise ValidationError("Voice ID cannot be empty", field="voice_id")

    if not (0.5 <= speed <= 2.0):
        raise ValidationError(
            "Speed must be between 0.5 and 2.0", field="speed", details={"speed": speed}
        )

    if not (-12 <= pitch <= 12):
        raise ValidationError(
            "Pitch must be between -12 and 12 semitones", field="pitch", details={"pitch": pitch}
        )

    allowed_formats = ["wav", "mp3", "ogg"]
    if output_format not in allowed_formats:
        raise ValidationError(
            f"Invalid output format. Allowed: {', '.join(allowed_formats)}",
            field="output_format",
            details={"allowed_formats": allowed_formats, "provided_format": output_format},
        )

    task_id = str(uuid4())

    try:
        tts_tasks[task_id] = {"status": "processing"}

        background_tasks.add_task(
            process_tts,
            task_id,
            text,
            voice_id,
            speed=speed,
            pitch=pitch,
            output_format=output_format,
        )

        logger.info("TTS task created", extra={"task_id": task_id})
        return {"task_id": task_id}
    except Exception as e:
        logger.error(
            "Failed to create TTS task", extra={"task_id": task_id, "error": str(e)}, exc_info=True
        )
        raise ExternalServiceError("TTS service", "Failed to process request")


@app.get("/api/tts/{task_id}")
async def tts_status(task_id: str):
    """
    Get the status of a TTS synthesis task.

    Args:
        task_id: Task identifier

    Returns:
        Task status and result if completed
    """
    if task_id not in tts_tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    return tts_tasks[task_id]


@app.get("/api/tts/audio/{task_id}")
async def tts_audio(task_id: str):
    """
    Get the generated audio for a completed TTS task.

    Args:
        task_id: Task identifier

    Returns:
        Audio file response
    """
    if task_id not in tts_tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = tts_tasks[task_id]
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="Task not completed")

    import base64

    audio_data = base64.b64decode(task["audio_data"])

    from fastapi.responses import Response

    return Response(
        content=audio_data,
        media_type="audio/wav",
        headers={"Content-Disposition": f"attachment; filename={task['filename']}"},
    )


@app.post("/api/audiobook")
async def audiobook_generate(
    text: str = Form(...),
    output_format: str = Form("wav"),
    sample_rate: int = Form(22050),
    normalize: bool = Form(True),
    chapter_markers: bool = Form(True),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """
    Generate an audiobook from markup text.

    Args:
        text: Text with triple-brace markup
        output_format: Output audio format
        sample_rate: Audio sample rate
        normalize: Whether to normalize audio
        chapter_markers: Whether to add chapter markers

    Returns:
        Task ID for tracking generation progress
    """
    if not text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    # Validate markup
    validation_issues = validate_audiobook_markup(text)
    if validation_issues:
        raise HTTPException(
            status_code=400, detail=f"Invalid markup: {'; '.join(validation_issues)}"
        )

    task_id = str(uuid4())

    audiobook_tasks[task_id] = {"status": "processing"}

    background_tasks.add_task(
        process_audiobook,
        task_id,
        text,
        output_format=output_format,
        sample_rate=sample_rate,
        normalize=normalize,
        chapter_markers=chapter_markers,
    )

    return {"task_id": task_id}


@app.get("/api/audiobook/{task_id}")
async def audiobook_status(task_id: str):
    """
    Get the status of an audiobook generation task.

    Args:
        task_id: Task identifier

    Returns:
        Task status and result if completed
    """
    if task_id not in audiobook_tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    return audiobook_tasks[task_id]


@app.get("/api/audiobook/audio/{task_id}")
async def audiobook_audio(task_id: str):
    """
    Get the generated audiobook for a completed task.

    Args:
        task_id: Task identifier

    Returns:
        Audio file response
    """
    if task_id not in audiobook_tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = audiobook_tasks[task_id]
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="Task not completed")

    import base64

    audio_data = base64.b64decode(task["audio_data"])

    from fastapi.responses import Response

    return Response(
        content=audio_data,
        media_type="audio/wav",
        headers={"Content-Disposition": f"attachment; filename={task['filename']}"},
    )


@app.post("/api/sounds/effects")
async def upload_sound_effect(
    file: UploadFile = File(..., alias="audio_file"),
    name: str = Form(""),
    id: str = Form(""),
    category: str = Form(""),
    volume: float = Form(0.8),
    fade_in: float = Form(0.0),
    fade_out: float = Form(0.0),
    duration: float = Form(None),
    pause_speech: bool = Form(False),
):
    """
    Upload a sound effect with metadata.

    Args:
        file: Audio file to upload
        name: Display name for the sound effect
        id: Unique identifier
        category: Category for organization
        volume: Default volume
        fade_in: Fade in time
        fade_out: Fade out time
        duration: Max duration
        pause_speech: Whether to pause speech

    Returns:
        Upload result with sound ID
    """
    validate_audio_file(file)

    if not id:
        raise HTTPException(status_code=400, detail="Sound effect ID is required")

    metadata = {
        "id": id,
        "name": name or Path(file.filename).stem,
        "category": category,
        "volume": volume,
        "fade_in": fade_in,
        "fade_out": fade_out,
        "duration": duration,
        "pause_speech": pause_speech,
        "type": "effect",
    }

    sound_id = save_sound_file(SFX_DIR, file, metadata)

    return {"id": sound_id, "message": "Sound effect uploaded successfully"}


@app.get("/api/sounds/effects")
async def list_sound_effects():
    """
    Get list of all sound effects.

    Returns:
        List of sound effect metadata
    """
    return list_sounds(SFX_DIR)


@app.post("/api/sounds/background")
async def upload_background_audio(
    file: UploadFile = File(..., alias="audio_file"),
    name: str = Form(""),
    id: str = Form(""),
    type: str = Form("ambient"),
    volume: float = Form(0.3),
    fade_in: float = Form(1.0),
    fade_out: float = Form(1.0),
    duck_level: float = Form(0.2),
    loop: bool = Form(True),
    duck_speech: bool = Form(True),
):
    """
    Upload background audio with metadata.

    Args:
        file: Audio file to upload
        name: Display name for the background audio
        id: Unique identifier
        type: Type of background audio
        volume: Default volume
        fade_in: Fade in time
        fade_out: Fade out time
        duck_level: Volume level when ducking
        loop: Whether to loop
        duck_speech: Whether to duck speech

    Returns:
        Upload result with sound ID
    """
    validate_audio_file(file)

    if not id:
        raise HTTPException(status_code=400, detail="Background audio ID is required")

    metadata = {
        "id": id,
        "name": name or Path(file.filename).stem,
        "type": type,
        "volume": volume,
        "fade_in": fade_in,
        "fade_out": fade_out,
        "duck_level": duck_level,
        "loop": loop,
        "duck_speech": duck_speech,
        "audio_type": "background",
    }

    sound_id = save_sound_file(BACKGROUND_DIR, file, metadata)

    return {"id": sound_id, "message": "Background audio uploaded successfully"}


@app.get("/api/sounds/background")
async def list_background_audio():
    """
    Get list of all background audio tracks.

    Returns:
        List of background audio metadata
    """
    return list_sounds(BACKGROUND_DIR)


@app.get("/api/sounds/effects/{sound_id}")
async def get_sound_effect(sound_id: str):
    """
    Get metadata for a specific sound effect.

    Args:
        sound_id: Sound effect ID

    Returns:
        Sound effect metadata
    """
    metadata_path = SFX_DIR / f"{sound_id}.json"
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="Sound effect not found")

    with open(metadata_path) as f:
        return json.load(f)


@app.get("/api/sounds/background/{sound_id}")
async def get_background_audio(sound_id: str):
    """
    Get metadata for a specific background audio.

    Args:
        sound_id: Background audio ID

    Returns:
        Background audio metadata
    """
    metadata_path = BACKGROUND_DIR / f"{sound_id}.json"
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="Background audio not found")

    with open(metadata_path) as f:
        return json.load(f)


@app.get("/api/sounds/effects/{sound_id}/audio")
async def get_sound_effect_audio(sound_id: str):
    """
    Get the audio file for a sound effect.

    Args:
        sound_id: Sound effect ID

    Returns:
        Audio file response
    """
    metadata = await get_sound_effect(sound_id)
    audio_path = SFX_DIR / metadata["filename"]

    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")

    return Response(
        content=audio_path.read_bytes(),
        media_type=metadata["content_type"],
        headers={"Content-Disposition": f"attachment; filename={metadata['filename']}"},
    )


@app.get("/api/sounds/background/{sound_id}/audio")
async def get_background_audio_file(sound_id: str):
    """
    Get the audio file for background audio.

    Args:
        sound_id: Background audio ID

    Returns:
        Audio file response
    """
    metadata = await get_background_audio(sound_id)
    audio_path = BACKGROUND_DIR / metadata["filename"]

    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")

    return Response(
        content=audio_path.read_bytes(),
        media_type=metadata["content_type"],
        headers={"Content-Disposition": f"attachment; filename={metadata['filename']}"},
    )


@app.put("/api/sounds/effects/{sound_id}")
async def update_sound_effect(
    sound_id: str,
    name: str = Form(None),
    category: str = Form(None),
    volume: float = Form(None),
    fade_in: float = Form(None),
    fade_out: float = Form(None),
    duration: float = Form(None),
    pause_speech: bool = Form(None),
):
    """
    Update metadata for a sound effect.

    Args:
        sound_id: Sound effect ID
        Other params: Fields to update

    Returns:
        Updated metadata
    """
    metadata_path = SFX_DIR / f"{sound_id}.json"
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="Sound effect not found")

    with open(metadata_path) as f:
        metadata = json.load(f)

    # Update only provided fields
    updates = {
        k: v
        for k, v in {
            "name": name,
            "category": category,
            "volume": volume,
            "fade_in": fade_in,
            "fade_out": fade_out,
            "duration": duration,
            "pause_speech": pause_speech,
        }.items()
        if v is not None
    }

    metadata.update(updates)

    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    return metadata


@app.put("/api/sounds/background/{sound_id}")
async def update_background_audio(
    sound_id: str,
    name: str = Form(None),
    type: str = Form(None),
    volume: float = Form(None),
    fade_in: float = Form(None),
    fade_out: float = Form(None),
    duck_level: float = Form(None),
    loop: bool = Form(None),
    duck_speech: bool = Form(None),
):
    """
    Update metadata for background audio.

    Args:
        sound_id: Background audio ID
        Other params: Fields to update

    Returns:
        Updated metadata
    """
    metadata_path = BACKGROUND_DIR / f"{sound_id}.json"
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="Background audio not found")

    with open(metadata_path) as f:
        metadata = json.load(f)

    # Update only provided fields
    updates = {
        k: v
        for k, v in {
            "name": name,
            "type": type,
            "volume": volume,
            "fade_in": fade_in,
            "fade_out": fade_out,
            "duck_level": duck_level,
            "loop": loop,
            "duck_speech": duck_speech,
        }.items()
        if v is not None
    }

    metadata.update(updates)

    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    return metadata


@app.delete("/api/sounds/effects/{sound_id}")
async def delete_sound_effect(sound_id: str):
    """
    Delete a sound effect.

    Args:
        sound_id: Sound effect ID

    Returns:
        Success message
    """
    metadata_path = SFX_DIR / f"{sound_id}.json"
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="Sound effect not found")

    with open(metadata_path) as f:
        metadata = json.load(f)

    # Delete files
    audio_path = SFX_DIR / metadata["filename"]
    if audio_path.exists():
        audio_path.unlink()
    metadata_path.unlink()

    return {"message": "Sound effect deleted successfully"}


@app.delete("/api/sounds/background/{sound_id}")
async def delete_background_audio(sound_id: str):
    """
    Delete background audio.

    Args:
        sound_id: Background audio ID

    Returns:
        Success message
    """
    metadata_path = BACKGROUND_DIR / f"{sound_id}.json"
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="Background audio not found")

    with open(metadata_path) as f:
        metadata = json.load(f)

    # Delete files
    audio_path = BACKGROUND_DIR / metadata["filename"]
    if audio_path.exists():
        audio_path.unlink()
    metadata_path.unlink()

    return {"message": "Background audio deleted successfully"}


@app.websocket("/ws/conversation")
async def conversation_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time conversation with bidirectional audio streaming.

    Handles wake word detection, real-time STT/TTS processing, and audio data exchange.
    """
    client_ip = websocket.client.host if websocket.client else "unknown"
    logger.info("WebSocket connection attempt", extra={"client_ip": client_ip})

    await websocket.accept()
    logger.info("WebSocket connection accepted", extra={"client_ip": client_ip})

    # Start a new conversation
    conversation_id = await conversation_manager.start_conversation(websocket)
    logger.info(
        "Conversation started", extra={"conversation_id": conversation_id, "client_ip": client_ip}
    )

    try:
        # Send initial connection confirmation
        await websocket.send_json({"type": "connected", "conversation_id": conversation_id})

        while True:
            try:
                # Receive message from frontend
                message = await websocket.receive_text()
                message_data = json.loads(message)
                message_type = message_data.get("type", "unknown")
                logger.debug(
                    "Received WebSocket message",
                    extra={
                        "conversation_id": conversation_id,
                        "message_type": message_type,
                        "client_ip": client_ip,
                    },
                )

                await conversation_manager.handle_frontend_message(
                    conversation_id, websocket, message
                )
            except json.JSONDecodeError as e:
                logger.warning(
                    "Invalid JSON in WebSocket message",
                    extra={
                        "conversation_id": conversation_id,
                        "client_ip": client_ip,
                        "error": str(e),
                    },
                )
                break
            except Exception as e:
                logger.error(
                    "Error handling WebSocket message",
                    extra={
                        "conversation_id": conversation_id,
                        "client_ip": client_ip,
                        "error": str(e),
                    },
                    exc_info=True,
                )
                break

    except WebSocketDisconnect:
        logger.info(
            "WebSocket disconnected",
            extra={"conversation_id": conversation_id, "client_ip": client_ip},
        )
    except Exception as e:
        logger.error(
            "WebSocket error",
            extra={"conversation_id": conversation_id, "client_ip": client_ip, "error": str(e)},
            exc_info=True,
        )
    finally:
        # Clean up the conversation
        await conversation_manager.remove_frontend_connection(conversation_id, websocket)
        logger.info(
            "WebSocket connection cleanup completed",
            extra={"conversation_id": conversation_id, "client_ip": client_ip},
        )


@app.get("/conversation", response_class=HTMLResponse)
async def conversation_interface(request: Request):
    """Real-time conversation interface page."""
    return templates.TemplateResponse("conversation.html", {"request": request})


@app.get("/settings", response_class=HTMLResponse)
async def settings(request: Request):
    """Settings page."""
    return templates.TemplateResponse("settings.html", {"request": request})
