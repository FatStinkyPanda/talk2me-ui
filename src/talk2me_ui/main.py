"""Main FastAPI application for Talk2Me UI.

This module sets up the FastAPI application with Jinja2 templates,
static file serving, CORS middleware, and route handlers for all
main sections of the application.
"""

import io
import json
import logging
import logging.config
import math
import os
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml
from dotenv import load_dotenv
from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydub import AudioSegment

from .api_client import Talk2MeAPIClient
from .auth import generate_session_cookie, session_manager, user_manager
from .auth_middleware import AuthenticationMiddleware
from .cache import cached_api_response, start_cache_cleanup, voice_cache
from .conversation_manager import conversation_manager
from .csrf import CSRFMiddleware, get_csrf_context
from .database import init_db
from .db_managers import db_sound_manager
from .exceptions import (
    ExternalServiceError,
    NotFoundError,
    Talk2MeException,
    ValidationError,
    handle_exception,
)
from .file_handler import get_streaming_handler
from .i18n import get_template_context
from .markup_parser import MarkupSection, parse_audiobook_markup, validate_audiobook_markup
from .memory_monitor import optimize_memory, start_memory_monitoring
from .plugins import PluginManager
from .plugins.interfaces import PluginContext
from .rbac import rbac_manager, require_permission
from .security_headers import SecurityHeadersConfig, SecurityHeadersMiddleware
from .security_middleware import (
    ContentSecurityMiddleware,
    RequestLoggingMiddleware,
    SecurityMiddleware,
)
from .validation import (
    InputSanitizer,
    validate_environment_on_startup,
    validate_text_input,
    validation_middleware,
)

# Load environment variables from .env files
load_dotenv(".env.dev" if os.getenv("APP_ENV") == "development" else ".env.prod")


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
    """Set up structured logging configuration.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path
    """
    # Convert string log level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Base configuration
    config: dict[str, Any] = {
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

# Start memory monitoring
start_memory_monitoring()

# Validate environment variables on startup
validate_environment_on_startup()

# Create FastAPI app instance
app = FastAPI(
    title="Talk2Me UI",
    description="Web interface for Talk2Me speech processing services",
    version="1.0.0",
)

# Initialize API client
api_client = Talk2MeAPIClient()

# Initialize plugin system
plugin_context = PluginContext(
    app_config={},  # Will be populated from config
    database_manager=None,  # Will be set after initialization
    api_client=api_client,
    user_manager=user_manager,
    cache_manager=voice_cache,  # Using voice cache as general cache manager
)

plugins_dir = Path("data/plugins")
plugin_manager = PluginManager(plugins_dir, plugin_context)


@app.on_event("startup")
async def startup_event():
    """Application startup event handler."""
    # Initialize database
    init_db()

    # Initialize RBAC system
    rbac_manager.initialize_default_roles_and_permissions()
    logger.info("RBAC system initialized")

    # Start cache cleanup task
    start_cache_cleanup()

    # Initialize plugin system
    await plugin_manager.initialize()
    logger.info("Plugin system initialized")

    logger.info("Application startup completed")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event handler."""
    # Shutdown plugin system
    await plugin_manager.shutdown()
    logger.info("Plugin system shutdown completed")

    logger.info("Application shutdown completed")


# Load custom OpenAPI specification
try:
    with open("openapi.yaml") as f:
        custom_openapi = yaml.safe_load(f)
    app.openapi_schema = custom_openapi
    logging.getLogger("talk2me_ui.main").info("Custom OpenAPI specification loaded successfully")
except FileNotFoundError:
    logging.getLogger("talk2me_ui.main").info(
        "openapi.yaml not found, using default OpenAPI schema"
    )
except Exception as e:
    logging.getLogger("talk2me_ui.main").warning(
        f"Failed to load custom OpenAPI spec: {e}, using default schema"
    )

# Configure Jinja2 templates with CSRF and i18n context
templates = Jinja2Templates(directory="src/talk2me_ui/templates")


# Add CSRF, i18n, and permission context to all templates
def check_template_permission(resource: str, action: str) -> bool:
    """Check permission for template rendering."""
    request = None
    # This function will be called during template rendering
    # We need to get the current request from the template context
    # For now, return True if no user context (will be filtered by middleware)
    try:
        # This is a bit of a hack - in a real implementation, you'd pass the request
        # or user context to the template context
        return True  # Allow by default, middleware will enforce
    except:
        return True


templates.env.globals.update(
    get_csrf_context=get_csrf_context,
    check_permission=check_template_permission,
    **get_template_context(),
)

# Mount static files
app.mount("/static", StaticFiles(directory="src/talk2me_ui/static"), name="static")

# Prometheus metrics
request_count = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "endpoint", "status_code"]
)

request_duration = Histogram(
    "http_request_duration_seconds", "HTTP request duration in seconds", ["method", "endpoint"]
)

stt_tasks_total = Counter("stt_tasks_total", "Total STT tasks processed", ["status"])

tts_tasks_total = Counter("tts_tasks_total", "Total TTS tasks processed", ["status"])

audiobook_tasks_total = Counter(
    "audiobook_tasks_total", "Total audiobook tasks processed", ["status"]
)

audio_processing_duration = Histogram(
    "audio_processing_duration_seconds", "Audio processing duration in seconds", ["task_type"]
)

# Add security middleware (order matters - security first)
app_env = os.getenv("APP_ENV", "development")

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware, log_sensitive_headers=False)

# Add content security middleware
app.add_middleware(ContentSecurityMiddleware)

# Add host validation middleware
allowed_hosts = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
app.add_middleware(SecurityMiddleware, allowed_hosts=allowed_hosts)

# Add security headers middleware
if app_env == "production":
    headers_config = SecurityHeadersConfig.get_production_config()
else:
    headers_config = SecurityHeadersConfig.get_development_config()

app.add_middleware(SecurityHeadersMiddleware, **headers_config)

# Add CSRF protection middleware
csrf_secret = os.getenv("CSRF_SECRET", "default-csrf-secret-change-in-production")
app.add_middleware(
    CSRFMiddleware,
    secret_key=csrf_secret,
    exempt_paths=[
        "/api/health",
        "/metrics",
        "/api/stt",  # File uploads need special handling
        "/api/voices",  # File uploads
        "/api/sounds/effects",  # File uploads
        "/api/sounds/background",  # File uploads
        "/auth/login",  # Auth endpoints
        "/auth/register",
    ],
)

# Add authentication middleware
app.add_middleware(
    AuthenticationMiddleware,
    exclude_paths=[
        "/auth/login",
        "/auth/register",
        "/api/health",
        "/metrics",
        "/static",
        "/favicon.ico",
    ],
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "X-CSRF-Token"],
)


# Add metrics middleware
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Middleware to collect HTTP request metrics."""
    start_time = time.time()

    # Get endpoint name (remove leading /api/ for cleaner metrics)
    endpoint = request.url.path
    if endpoint.startswith("/api/"):
        endpoint = endpoint[4:]  # Remove /api/ prefix
    elif endpoint == "/":
        endpoint = "root"
    else:
        endpoint = endpoint.lstrip("/").replace("/", "_")

    try:
        response = await call_next(request)
        status_code = str(response.status_code)

        # Record metrics
        request_count.labels(
            method=request.method, endpoint=endpoint, status_code=status_code
        ).inc()

        request_duration.labels(method=request.method, endpoint=endpoint).observe(
            time.time() - start_time
        )

        return response
    except Exception:
        # Record error metrics
        request_count.labels(method=request.method, endpoint=endpoint, status_code="500").inc()

        request_duration.labels(method=request.method, endpoint=endpoint).observe(
            time.time() - start_time
        )

        raise


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


# Set up logging with contextual information
logger = logging.getLogger("talk2me_ui.main")

# Global dictionaries to track tasks
stt_tasks: dict[str, dict[str, Any]] = {}
tts_tasks: dict[str, dict[str, Any]] = {}
audiobook_tasks: dict[str, dict[str, Any]] = {}

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


async def process_stt(task_id: str, tmp_path: str, sample_rate: int | None = None):
    """Background task to process STT transcription.

    Args:
        task_id: Unique task identifier
        tmp_path: Path to temporary audio file
        sample_rate: Optional sample rate override
    """
    start_time = time.time()
    logger.info(
        "Starting STT transcription", extra={"task_id": task_id, "sample_rate": sample_rate}
    )
    try:
        with open(tmp_path, "rb") as f:
            result = api_client.stt_transcribe(f, sample_rate)
        stt_tasks[task_id] = {"status": "completed", "result": result}
        stt_tasks_total.labels(status="completed").inc()
        audio_processing_duration.labels(task_type="stt").observe(time.time() - start_time)
        logger.info(
            "STT transcription completed",
            extra={"task_id": task_id, "text_length": len(result.get("text", ""))},
        )
    except Exception as e:
        logger.error(
            "STT transcription failed", extra={"task_id": task_id, "error": str(e)}, exc_info=True
        )
        stt_tasks[task_id] = {"status": "failed", "error": str(e)}
        stt_tasks_total.labels(status="failed").inc()
        audio_processing_duration.labels(task_type="stt").observe(time.time() - start_time)
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
    """Background task to process TTS synthesis.

    Args:
        task_id: Unique task identifier
        text: Text to synthesize
        voice: Voice identifier
        **kwargs: Additional parameters
    """
    start_time = time.time()
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
        tts_tasks_total.labels(status="completed").inc()
        audio_processing_duration.labels(task_type="tts").observe(time.time() - start_time)
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
        tts_tasks_total.labels(status="failed").inc()
        audio_processing_duration.labels(task_type="tts").observe(time.time() - start_time)


def load_sound_effect(sfx_config: dict, task_id: str) -> AudioSegment | None:
    """Load and process a sound effect.

    Args:
        sfx_config: Sound effect configuration
        task_id: Task identifier for logging

    Returns:
        Processed AudioSegment or None if loading fails
    """
    sfx_id = sfx_config["id"]
    sound = db_sound_manager.get_sound(sfx_id)
    if not sound:
        logger.warning(f"Sound effect not found: {sfx_id}", extra={"task_id": task_id})
        return None

    audio_path = SFX_DIR / sound.filename
    if not audio_path.exists():
        logger.warning(
            f"Sound effect audio file not found: {audio_path}", extra={"task_id": task_id}
        )
        return None

    segment = AudioSegment.from_file(audio_path)

    # Apply volume
    volume = sfx_config.get("volume", sound.volume)
    segment = segment + (20 * math.log10(volume))  # dB adjustment

    # Apply fade in/out
    fade_in = sfx_config.get("fade_in", sound.fade_in)
    fade_out = sfx_config.get("fade_out", sound.fade_out)
    if fade_in > 0:
        segment = segment.fade_in(int(fade_in * 1000))
    if fade_out > 0:
        segment = segment.fade_out(int(fade_out * 1000))

    # Apply duration limit
    duration = sfx_config.get("duration") or sound.duration
    if duration:
        segment = segment[: int(duration * 1000)]

    return segment


def load_background_audio(bg_config: dict, task_id: str) -> AudioSegment | None:
    """Load and process background audio.

    Args:
        bg_config: Background audio configuration
        task_id: Task identifier for logging

    Returns:
        Processed AudioSegment or None if loading fails
    """
    bg_name = bg_config["name"]
    # For background audio, we need to find by name since the config uses name, not id
    # This is a bit of a hack - ideally the config should use IDs
    sounds = db_sound_manager.list_sounds(sound_type="background")
    sound = next((s for s in sounds if s.name == bg_name), None)
    if not sound:
        logger.warning(f"Background audio not found: {bg_name}", extra={"task_id": task_id})
        return None

    audio_path = BACKGROUND_DIR / sound.filename
    if not audio_path.exists():
        logger.warning(f"Background audio file not found: {audio_path}", extra={"task_id": task_id})
        return None

    segment = AudioSegment.from_file(audio_path)

    # Apply volume
    volume = bg_config.get("volume", sound.volume)
    segment = segment + (20 * math.log10(volume))  # dB adjustment

    # Apply fade in/out
    fade_in = bg_config.get("fade_in", sound.fade_in)
    fade_out = bg_config.get("fade_out", sound.fade_out)
    if fade_in > 0:
        segment = segment.fade_in(int(fade_in * 1000))
    if fade_out > 0:
        segment = segment.fade_out(int(fade_out * 1000))

    return segment


def process_background_audio_change(
    section: MarkupSection,
    active_bg: tuple[float, dict[str, Any]] | None,
    current_time: float,
    audio_events: list[tuple[float, AudioSegment]],
    task_id: str,
) -> tuple[float, dict[str, Any]] | None:
    """Process background audio changes for a section.

    Args:
        section: Current section being processed
        active_bg: Currently active background (start_time, bg_config)
        current_time: Current timeline position
        audio_events: List to append audio events to
        task_id: Task identifier for logging

    Returns:
        Updated active_bg tuple
    """
    # Handle background audio changes
    if section.background_audio:
        # Stop previous bg if any
        if active_bg:
            start_time, bg_config = active_bg
            bg_segment = load_background_audio(bg_config, task_id)
            if bg_segment:
                duration = current_time - start_time
                audio_events.append(
                    (
                        start_time,
                        create_looped_segment(bg_segment, duration, bg_config.get("loop", True)),
                    )
                )

        # Start new bg
        active_bg = (current_time, section.background_audio)
    elif active_bg and section.background_audio is None:
        # Explicit stop
        start_time, bg_config = active_bg
        bg_segment = load_background_audio(bg_config, task_id)
        if bg_segment:
            duration = current_time - start_time
            audio_events.append(
                (
                    start_time,
                    create_looped_segment(bg_segment, duration, bg_config.get("loop", True)),
                )
            )
        active_bg = None

    return active_bg


def create_looped_segment(
    segment: AudioSegment, duration_ms: float, loop: bool = True
) -> AudioSegment:
    """Create a looped or truncated audio segment for the given duration.

    Args:
        segment: Base audio segment
        duration_ms: Desired duration in milliseconds
        loop: Whether to loop the segment

    Returns:
        AudioSegment of the desired duration
    """
    if loop:
        # Loop the segment for the duration
        looped_segment = AudioSegment.empty()
        while looped_segment.duration_seconds < (duration_ms / 1000):
            remaining = (duration_ms / 1000) - looped_segment.duration_seconds
            if remaining >= segment.duration_seconds:
                looped_segment += segment
            else:
                looped_segment += segment[: int(remaining * 1000)]
        return looped_segment
    else:
        # Non-looping, take duration
        return segment[: int(duration_ms)]


def generate_voice_audio(section, task_id, **kwargs) -> AudioSegment:
    """Generate voice audio for a section.

    Args:
        section: Section containing text and voice
        task_id: Task identifier for logging
        **kwargs: Additional TTS parameters

    Returns:
        AudioSegment of generated voice

    Raises:
        ValueError: If no voice specified for section
    """
    if not section.voice:
        raise ValueError(f"No voice specified for section: {section.text[:50]}...")

    logger.debug(
        "Generating TTS for section",
        extra={
            "task_id": task_id,
            "voice": section.voice,
            "text_length": len(section.text),
        },
    )
    audio_data = api_client.tts_synthesize(section.text, section.voice, **kwargs)
    return AudioSegment.from_wav(io.BytesIO(audio_data))


def mix_audio_events(audio_events: list) -> AudioSegment:
    """Mix all audio events into a single audio segment.

    Args:
        audio_events: List of (start_time, segment) tuples

    Returns:
        Combined AudioSegment
    """
    if not audio_events:
        return AudioSegment.empty()

    # Find total duration
    max_end_time = max(start + len(segment) for start, segment in audio_events)
    combined_audio = AudioSegment.silent(duration=max_end_time)

    # Overlay all segments
    for start_time, segment in audio_events:
        combined_audio = combined_audio.overlay(segment, position=int(start_time))

    return combined_audio


async def process_audiobook(task_id: str, markup_text: str, **kwargs):
    """Background task to process audiobook generation from markup.

    Args:
        task_id: Unique task identifier
        markup_text: Text with triple-brace markup
        **kwargs: Additional parameters
    """
    start_time = time.time()
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

        # Generate audio for each section with mixing

        # Collect all audio events with timing
        audio_events: list[tuple[float, AudioSegment]] = []
        current_time = 0.0  # in milliseconds
        active_bg = None  # (start_time, bg_config)

        for _i, section in enumerate(sections):
            # Handle background audio changes
            active_bg = process_background_audio_change(
                section, active_bg, current_time, audio_events, task_id
            )

            # Handle sound effects
            for sfx_config in section.sound_effects:
                sfx_segment = load_sound_effect(sfx_config, task_id)
                if sfx_segment:
                    start_at = sfx_config.get("start_at", 0.0)
                    sfx_start = current_time + (start_at * 1000)
                    audio_events.append((sfx_start, sfx_segment))

            # Handle voice/text
            if section.text.strip():
                voice_segment = generate_voice_audio(section, task_id, **kwargs)
                audio_events.append((current_time, voice_segment))
                current_time += len(voice_segment)

        # Handle final background audio
        if active_bg:
            start_time, bg_config = active_bg
            bg_segment = load_background_audio(bg_config, task_id)
            if bg_segment:
                duration = current_time - start_time
                audio_events.append(
                    (
                        start_time,
                        create_looped_segment(bg_segment, duration, bg_config.get("loop", True)),
                    )
                )

        # Mix all audio events
        combined_audio = mix_audio_events(audio_events)

        # Force garbage collection after mixing to free memory
        optimize_memory()

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
        audiobook_tasks_total.labels(status="completed").inc()
        audio_processing_duration.labels(task_type="audiobook").observe(time.time() - start_time)
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
        audiobook_tasks_total.labels(status="failed").inc()
        audio_processing_duration.labels(task_type="audiobook").observe(time.time() - start_time)


def validate_audio_file(file: UploadFile) -> None:
    """Validate uploaded audio file.

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


def save_sound_file(directory: Path, file_path: Path, metadata: dict, user_id: str) -> str:
    """Save sound file from temporary path and its metadata to database.

    Args:
        directory: Directory to save in (SFX_DIR or BACKGROUND_DIR)
        file_path: Path to the temporary file
        metadata: Metadata dictionary
        user_id: User ID who uploaded the sound

    Returns:
        User-provided ID of the sound
    """
    sound_id = str(metadata.get("id", str(uuid4())))
    file_ext = file_path.suffix.lower()

    # Save audio file
    audio_filename = f"{sound_id}{file_ext}"
    audio_path = directory / audio_filename

    logger.info(
        "Saving sound file",
        extra={
            "sound_id": sound_id,
            "directory": str(directory),
            "filename": audio_filename,
            "temp_path": str(file_path),
        },
    )

    # Move file from temp location to final location
    file_path.rename(audio_path)
    file_size = audio_path.stat().st_size

    # Prepare sound data for database
    sound_data = {
        "id": sound_id,
        "name": metadata["name"],
        "sound_type": metadata.get("type", "effect")
        .replace("effect", "effect")
        .replace("background", "background"),
        "category": metadata.get("category"),
        "volume": metadata.get("volume", 0.8),
        "fade_in": metadata.get("fade_in", 0.0),
        "fade_out": metadata.get("fade_out", 0.0),
        "duration": metadata.get("duration"),
        "pause_speech": metadata.get("pause_speech", False),
        "loop": metadata.get("loop", True),
        "duck_level": metadata.get("duck_level", 0.2),
        "duck_speech": metadata.get("duck_speech", True),
        "filename": audio_filename,
        "original_filename": metadata.get("original_filename", audio_filename),
        "content_type": metadata.get("content_type", "audio/wav"),
        "size": file_size,
    }

    # Save to database
    db_sound_manager.create_sound(sound_data, user_id)

    logger.info(
        "Sound file saved successfully",
        extra={
            "sound_id": sound_id,
            "audio_path": str(audio_path),
            "file_size": file_size,
        },
    )

    return sound_id


def list_sounds(directory: Path) -> list[dict]:
    """List all sounds in a directory with their metadata.

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
    """Handle Talk2Me custom exceptions with proper HTTP responses.

    Returns JSON error response for API routes, HTML for web routes.
    """
    logger.error(
        "Talk2Me exception occurred",
        extra={
            "error_code": exc.error_code,
            "error_message": exc.message,
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
    """Global exception handler for unhandled errors.

    Returns appropriate error response based on request type.
    """
    logger.error(
        "Unhandled exception occurred",
        extra={
            "error_type": type(exc).__name__,
            "error_message": str(exc),
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
    """Health check endpoint for monitoring and load balancers.

    Returns:
        Health status with basic system information
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "version": "1.0.0",
        "service": "talk2me-ui",
    }


# Memory optimization endpoint
@app.post("/api/admin/optimize-memory")
@require_permission("system", "admin")
async def optimize_memory_endpoint():
    """Trigger memory optimization operations.

    Returns:
        Optimization results
    """
    try:
        optimize_memory()
        return {"message": "Memory optimization completed successfully"}
    except Exception as e:
        logger.error(f"Memory optimization failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Memory optimization failed: {str(e)}")


# Prometheus metrics endpoint
@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint.

    Returns:
        Prometheus-formatted metrics data
    """
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# API Documentation endpoint
@app.get("/docs", response_class=HTMLResponse)
async def api_documentation(request: Request):
    """API documentation page with Swagger UI.

    Returns:
        HTML page with interactive API documentation
    """
    return templates.TemplateResponse("docs.html", {"request": request})


# Authentication routes


@app.get("/auth/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page."""
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/auth/login")
async def login(
    username: str = Form(...),
    password: str = Form(...),
    request: Request = None,
):
    """Authenticate user and create session."""
    try:
        user = user_manager.authenticate_user(username, password)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Create session
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        session = session_manager.create_session(
            user.id, ip_address=client_ip, user_agent=user_agent
        )

        # Create response
        response = RedirectResponse(url="/", status_code=302)

        # Set session cookie
        session_cookie = generate_session_cookie(session)
        response.set_cookie(
            key="session_id",
            value=session_cookie,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=24 * 60 * 60,  # 24 hours
            path="/",
        )

        logger.info(f"User {user.username} logged in successfully")
        return response

    except Exception as e:
        logger.warning(f"Login failed for {username}: {e}")
        raise HTTPException(status_code=401, detail="Invalid credentials") from None


@app.get("/auth/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Registration page."""
    return templates.TemplateResponse("register.html", {"request": request})


@app.post("/auth/register")
async def register(
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
):
    """Register a new user."""
    try:
        # Validate input
        if password != confirm_password:
            raise HTTPException(status_code=400, detail="Passwords do not match")

        if len(password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

        # Create user
        user = user_manager.create_user(username, email, password)

        logger.info(f"User {user.username} registered successfully")
        return RedirectResponse(url="/auth/login", status_code=302)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        raise HTTPException(status_code=500, detail="Registration failed") from None


@app.post("/auth/logout")
async def logout(request: Request):
    """Logout user and destroy session."""
    session_id = getattr(request.state, "session_id", None)
    if session_id:
        session_manager.delete_session(session_id)

    response = RedirectResponse(url="/auth/login", status_code=302)
    response.delete_cookie("session_id", path="/")
    return response


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
    audio_file: UploadFile = File(...),  # noqa: B008
    sample_rate: int = Form(None),
    background_tasks: BackgroundTasks = BackgroundTasks(),  # noqa: B008
):
    """Upload audio file for speech-to-text transcription.

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
        raise ExternalServiceError("STT service", "Failed to process upload") from e


@app.get("/api/stt/{task_id}")
async def stt_status(task_id: str):
    """Get the status of an STT transcription task.

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
@require_permission("voices", "view")
@cached_api_response(ttl=600, cache_instance=voice_cache)  # Cache for 10 minutes
async def list_voices():
    """Get list of available voices.

    Returns:
        List of voice objects
    """
    try:
        voices = api_client.list_voices()
        return voices
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/voices")
@require_permission("voices", "manage_own")
async def create_voice(
    name: str = Form(...),
    language: str = Form("en"),
    samples: list[UploadFile] | None = None,
):
    """Create a new voice profile.

    Args:
        name: Display name for the voice
        language: Language code
        samples: Audio sample files

    Returns:
        Voice creation response
    """
    # Validate inputs
    if not name.strip():
        raise ValidationError("Voice name cannot be empty", field="name")

    try:
        # Convert UploadFile to BinaryIO for api_client
        sample_files = []
        if samples:
            for sample in samples:
                if sample.filename:
                    sample_files.append(sample.file)

        result = api_client.create_voice(
            name=name, language=language, samples=sample_files if sample_files else None
        )
        return result
    except Exception as e:
        logger.error(
            "Voice creation failed",
            extra={"voice_name": name, "language": language, "error": str(e)},
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


def update_voice_metadata(voice_id: str, name: str | None, language: str | None) -> None:
    """Update voice metadata fields.

    Args:
        voice_id: Voice identifier
        name: New display name (optional)
        language: New language code (optional)

    Raises:
        Exception: If API call fails
    """
    update_data = {}
    if name is not None:
        update_data["name"] = name
    if language is not None:
        update_data["language"] = language

    if update_data:
        api_client.update_voice(voice_id, **update_data)


def upload_voice_samples(voice_id: str, samples: list[UploadFile] | None) -> None:
    """Upload additional voice samples.

    Args:
        voice_id: Voice identifier
        samples: List of sample files to upload

    Raises:
        Exception: If API call fails
    """
    if samples and any(sample.filename for sample in samples):
        sample_files = [sample.file for sample in samples if sample.filename]
        if sample_files:
            api_client.clone_voice(voice_id, sample_files)


@app.put("/api/voices/{voice_id}")
async def update_voice(
    voice_id: str,
    name: str = Form(None),
    language: str = Form(None),
    samples: list[UploadFile] | None = None,
):
    """Update a voice profile.

    Args:
        voice_id: Voice identifier
        name: New display name (optional)
        language: New language code (optional)
        samples: Additional audio sample files (optional)

    Returns:
        Voice update response
    """
    try:
        update_voice_metadata(voice_id, name, language)
        upload_voice_samples(voice_id, samples)

        return {"message": "Voice updated successfully"}
    except Exception as e:
        logger.error(
            "Voice update failed", extra={"voice_id": voice_id, "error": str(e)}, exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.delete("/api/voices/{voice_id}")
@require_permission("voices", "manage_own")
async def delete_voice(voice_id: str):
    """Delete a voice profile.

    Args:
        voice_id: Voice identifier

    Returns:
        Deletion confirmation
    """
    try:
        result = api_client.delete_voice(voice_id)
        return result
    except Exception as e:
        logger.error(
            "Voice deletion failed", extra={"voice_id": voice_id, "error": str(e)}, exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/tts")
@validate_text_input(min_length=1, max_length=5000, disallow_html=True)
async def tts_generate(
    text: str = Form(...),
    voice_id: str = Form(...),
    speed: float = Form(1.0),
    pitch: int = Form(0),
    output_format: str = Form("wav"),
    background_tasks: BackgroundTasks = BackgroundTasks(),  # noqa: B008
):
    """Generate speech from text using specified voice and parameters.

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
        raise ExternalServiceError("TTS service", "Failed to process request") from e


@app.get("/api/tts/{task_id}")
async def tts_status(task_id: str):
    """Get the status of a TTS synthesis task.

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
    """Get the generated audio for a completed TTS task.

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

    audio_data = base64.b64decode(str(task["audio_data"]))

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
    background_tasks: BackgroundTasks = BackgroundTasks(),  # noqa: B008
):
    """Generate an audiobook from markup text.

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
    """Get the status of an audiobook generation task.

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
    """Get the generated audiobook for a completed task.

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
@require_permission("sounds", "upload")
async def upload_sound_effect(
    file: UploadFile = File(..., alias="audio_file"),  # noqa: B008
    name: str = Form(""),
    sound_id: str = Form(""),
    category: str = Form(""),
    volume: float = Form(0.8),
    fade_in: float = Form(0.0),
    fade_out: float = Form(0.0),
    duration: float = Form(None),
    pause_speech: bool = Form(False),
):
    """Upload a sound effect with metadata using streaming file handling.

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
    if not sound_id:
        raise HTTPException(status_code=400, detail="Sound effect ID is required")

    # Use streaming file handler for large files
    streaming_handler = get_streaming_handler()
    temp_path = streaming_handler.create_temp_file(".wav")

    try:
        # Stream file to temporary location
        await streaming_handler.validate_and_save_file(file, temp_path, ALLOWED_AUDIO_TYPES)

        metadata = {
            "id": sound_id,
            "name": name or Path(file.filename or "").stem,
            "category": category,
            "volume": volume,
            "fade_in": fade_in,
            "fade_out": fade_out,
            "duration": duration,
            "pause_speech": pause_speech,
            "type": "effect",
        }

        sound_id = save_sound_file(SFX_DIR, temp_path, metadata, request.state.user.id)

        return {"id": sound_id, "message": "Sound effect uploaded successfully"}

    finally:
        # Clean up temporary file
        streaming_handler.cleanup_temp_file(temp_path)


@app.get("/api/sounds/effects")
@cached_api_response(ttl=300)  # Cache for 5 minutes
async def list_sound_effects(page: int = 1, limit: int = 50):
    """Get list of sound effects with pagination.

    Args:
        page: Page number (1-based)
        limit: Number of items per page

    Returns:
        Paginated list of sound effect metadata
    """
    offset = (page - 1) * limit
    sounds = db_sound_manager.list_sounds(sound_type="effect", limit=limit, offset=offset)

    # Convert SQLAlchemy objects to dicts for API response
    items = []
    for sound in sounds:
        items.append(
            {
                "id": sound.id,
                "name": sound.name,
                "category": sound.category,
                "volume": sound.volume,
                "fade_in": sound.fade_in,
                "fade_out": sound.fade_out,
                "duration": sound.duration,
                "pause_speech": sound.pause_speech,
                "type": "effect",
                "filename": sound.filename,
                "original_filename": sound.original_filename,
                "content_type": sound.content_type,
                "size": sound.size,
                "uploaded_at": sound.uploaded_at.isoformat() if sound.uploaded_at else None,
            }
        )

    # For now, we don't have total count easily, so we'll estimate
    # In production, you'd want to add a count query
    return {
        "items": items,
        "total": len(items) + (1 if len(items) == limit else 0),  # Rough estimate
        "page": page,
        "limit": limit,
        "has_more": len(items) == limit,
    }


@app.post("/api/sounds/background")
async def upload_background_audio(
    file: UploadFile = File(..., alias="audio_file"),  # noqa: B008
    name: str = Form(""),
    sound_id: str = Form(""),
    sound_type: str = Form("ambient"),
    volume: float = Form(0.3),
    fade_in: float = Form(1.0),
    fade_out: float = Form(1.0),
    duck_level: float = Form(0.2),
    loop: bool = Form(True),
    duck_speech: bool = Form(True),
):
    """Upload background audio with metadata using streaming file handling.

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
    if not sound_id:
        raise HTTPException(status_code=400, detail="Background audio ID is required")

    # Use streaming file handler for large files
    streaming_handler = get_streaming_handler()
    temp_path = streaming_handler.create_temp_file(".wav")

    try:
        # Stream file to temporary location
        await streaming_handler.validate_and_save_file(file, temp_path, ALLOWED_AUDIO_TYPES)

        metadata = {
            "id": sound_id,
            "name": name or Path(file.filename or "").stem,
            "type": sound_type,
            "volume": volume,
            "fade_in": fade_in,
            "fade_out": fade_out,
            "duck_level": duck_level,
            "loop": loop,
            "duck_speech": duck_speech,
            "audio_type": "background",
        }

        sound_id = save_sound_file(BACKGROUND_DIR, temp_path, metadata, request.state.user.id)

        return {"id": sound_id, "message": "Background audio uploaded successfully"}

    finally:
        # Clean up temporary file
        streaming_handler.cleanup_temp_file(temp_path)


@app.get("/api/sounds/background")
@cached_api_response(ttl=300)  # Cache for 5 minutes
async def list_background_audio(page: int = 1, limit: int = 50):
    """Get list of background audio tracks with pagination.

    Args:
        page: Page number (1-based)
        limit: Number of items per page

    Returns:
        Paginated list of background audio metadata
    """
    offset = (page - 1) * limit
    sounds = db_sound_manager.list_sounds(sound_type="background", limit=limit, offset=offset)

    # Convert SQLAlchemy objects to dicts for API response
    items = []
    for sound in sounds:
        items.append(
            {
                "id": sound.id,
                "name": sound.name,
                "type": sound.sound_type,
                "volume": sound.volume,
                "fade_in": sound.fade_in,
                "fade_out": sound.fade_out,
                "duck_level": sound.duck_level,
                "loop": sound.loop,
                "duck_speech": sound.duck_speech,
                "audio_type": "background",
                "filename": sound.filename,
                "original_filename": sound.original_filename,
                "content_type": sound.content_type,
                "size": sound.size,
                "uploaded_at": sound.uploaded_at.isoformat() if sound.uploaded_at else None,
            }
        )

    return {
        "items": items,
        "total": len(items) + (1 if len(items) == limit else 0),  # Rough estimate
        "page": page,
        "limit": limit,
        "has_more": len(items) == limit,
    }


@app.get("/api/sounds/effects/{sound_id}")
async def get_sound_effect(sound_id: str):
    """Get metadata for a specific sound effect.

    Args:
        sound_id: Sound effect ID

    Returns:
        Sound effect metadata
    """
    sound = db_sound_manager.get_sound(sound_id)
    if not sound or sound.sound_type != "effect":
        raise HTTPException(status_code=404, detail="Sound effect not found")

    return {
        "id": sound.id,
        "name": sound.name,
        "category": sound.category,
        "volume": sound.volume,
        "fade_in": sound.fade_in,
        "fade_out": sound.fade_out,
        "duration": sound.duration,
        "pause_speech": sound.pause_speech,
        "type": "effect",
        "filename": sound.filename,
        "original_filename": sound.original_filename,
        "content_type": sound.content_type,
        "size": sound.size,
        "uploaded_at": sound.uploaded_at.isoformat() if sound.uploaded_at else None,
    }


@app.get("/api/sounds/background/{sound_id}")
async def get_background_audio(sound_id: str):
    """Get metadata for a specific background audio.

    Args:
        sound_id: Background audio ID

    Returns:
        Background audio metadata
    """
    sound = db_sound_manager.get_sound(sound_id)
    if not sound or sound.sound_type != "background":
        raise HTTPException(status_code=404, detail="Background audio not found")

    return {
        "id": sound.id,
        "name": sound.name,
        "type": sound.sound_type,
        "volume": sound.volume,
        "fade_in": sound.fade_in,
        "fade_out": sound.fade_out,
        "duck_level": sound.duck_level,
        "loop": sound.loop,
        "duck_speech": sound.duck_speech,
        "audio_type": "background",
        "filename": sound.filename,
        "original_filename": sound.original_filename,
        "content_type": sound.content_type,
        "size": sound.size,
        "uploaded_at": sound.uploaded_at.isoformat() if sound.uploaded_at else None,
    }


@app.get("/api/sounds/effects/{sound_id}/audio")
async def get_sound_effect_audio(sound_id: str):
    """Get the audio file for a sound effect.

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
    """Get the audio file for background audio.

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
    request: Request,
    name: str = Form(None),
    category: str = Form(None),
    volume: float = Form(None),
    fade_in: float = Form(None),
    fade_out: float = Form(None),
    duration: float = Form(None),
    pause_speech: bool = Form(None),
):
    """Update metadata for a sound effect.

    Args:
        sound_id: Sound effect ID
        Other params: Fields to update

    Returns:
        Updated metadata
    """
    # Check ownership - only allow updating user's own sounds
    sound = db_sound_manager.get_sound(sound_id)
    if not sound or sound.sound_type != "effect" or sound.user_id != request.state.user.id:
        raise HTTPException(status_code=404, detail="Sound effect not found")

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

    if updates:
        updated_sound = db_sound_manager.update_sound(sound_id, **updates)
        if not updated_sound:
            raise HTTPException(status_code=500, detail="Failed to update sound effect")

    # Return updated metadata
    sound = db_sound_manager.get_sound(sound_id)
    return {
        "id": sound.id,
        "name": sound.name,
        "category": sound.category,
        "volume": sound.volume,
        "fade_in": sound.fade_in,
        "fade_out": sound.fade_out,
        "duration": sound.duration,
        "pause_speech": sound.pause_speech,
        "type": "effect",
        "filename": sound.filename,
        "original_filename": sound.original_filename,
        "content_type": sound.content_type,
        "size": sound.size,
        "uploaded_at": sound.uploaded_at.isoformat() if sound.uploaded_at else None,
    }


@app.put("/api/sounds/background/{sound_id}")
async def update_background_audio(
    sound_id: str,
    request: Request,
    name: str = Form(None),
    sound_type: str = Form(None),
    volume: float = Form(None),
    fade_in: float = Form(None),
    fade_out: float = Form(None),
    duck_level: float = Form(None),
    loop: bool = Form(None),
    duck_speech: bool = Form(None),
):
    """Update metadata for background audio.

    Args:
        sound_id: Background audio ID
        Other params: Fields to update

    Returns:
        Updated metadata
    """
    # Check ownership - only allow updating user's own sounds
    sound = db_sound_manager.get_sound(sound_id)
    if not sound or sound.sound_type != "background" or sound.user_id != request.state.user.id:
        raise HTTPException(status_code=404, detail="Background audio not found")

    # Update only provided fields
    updates = {
        k: v
        for k, v in {
            "name": name,
            "sound_type": sound_type,
            "volume": volume,
            "fade_in": fade_in,
            "fade_out": fade_out,
            "duck_level": duck_level,
            "loop": loop,
            "duck_speech": duck_speech,
        }.items()
        if v is not None
    }

    if updates:
        updated_sound = db_sound_manager.update_sound(sound_id, **updates)
        if not updated_sound:
            raise HTTPException(status_code=500, detail="Failed to update background audio")

    # Return updated metadata
    sound = db_sound_manager.get_sound(sound_id)
    return {
        "id": sound.id,
        "name": sound.name,
        "type": sound.sound_type,
        "volume": sound.volume,
        "fade_in": sound.fade_in,
        "fade_out": sound.fade_out,
        "duck_level": sound.duck_level,
        "loop": sound.loop,
        "duck_speech": sound.duck_speech,
        "audio_type": "background",
        "filename": sound.filename,
        "original_filename": sound.original_filename,
        "content_type": sound.content_type,
        "size": sound.size,
        "uploaded_at": sound.uploaded_at.isoformat() if sound.uploaded_at else None,
    }


@app.delete("/api/sounds/effects/{sound_id}")
async def delete_sound_effect(sound_id: str, request: Request):
    """Delete a sound effect.

    Args:
        sound_id: Sound effect ID

    Returns:
        Success message
    """
    # Check ownership - only allow deleting user's own sounds
    sound = db_sound_manager.get_sound(sound_id)
    if not sound or sound.sound_type != "effect" or sound.user_id != request.state.user.id:
        raise HTTPException(status_code=404, detail="Sound effect not found")

    # Delete audio file
    audio_path = SFX_DIR / sound.filename
    if audio_path.exists():
        audio_path.unlink()

    # Delete from database
    if not db_sound_manager.delete_sound(sound_id):
        raise HTTPException(status_code=500, detail="Failed to delete sound effect")

    return {"message": "Sound effect deleted successfully"}


@app.delete("/api/sounds/background/{sound_id}")
async def delete_background_audio(sound_id: str, request: Request):
    """Delete background audio.

    Args:
        sound_id: Background audio ID

    Returns:
        Success message
    """
    # Check ownership - only allow deleting user's own sounds
    sound = db_sound_manager.get_sound(sound_id)
    if not sound or sound.sound_type != "background" or sound.user_id != request.state.user.id:
        raise HTTPException(status_code=404, detail="Background audio not found")

    # Delete audio file
    audio_path = BACKGROUND_DIR / sound.filename
    if audio_path.exists():
        audio_path.unlink()

    # Delete from database
    if not db_sound_manager.delete_sound(sound_id):
        raise HTTPException(status_code=500, detail="Failed to delete background audio")

    return {"message": "Background audio deleted successfully"}


# Plugin management endpoints


@app.get("/api/plugins")
async def list_installed_plugins():
    """Get list of installed plugins."""
    try:
        plugins = await plugin_manager.marketplace.get_installed_plugins()
        return {"plugins": plugins}
    except Exception as e:
        logger.error(f"Failed to list plugins: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list plugins")


@app.get("/api/plugins/{plugin_name}")
async def get_plugin_info(plugin_name: str):
    """Get information about a specific plugin."""
    try:
        plugin_info = await plugin_manager.discovery.get_plugin_info(plugin_name)
        if not plugin_info:
            raise HTTPException(status_code=404, detail="Plugin not found")

        # Add runtime status
        plugin_info["active"] = plugin_manager.lifecycle.is_plugin_active(plugin_name)
        plugin_info["status"] = plugin_manager.lifecycle.get_plugin_state(plugin_name)

        return plugin_info
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get plugin info for {plugin_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get plugin information")


@app.post("/api/plugins/{plugin_name}/activate")
@require_permission("plugins", "manage")
async def activate_plugin(plugin_name: str):
    """Activate a plugin."""
    try:
        if plugin_manager.lifecycle.is_plugin_active(plugin_name):
            return {"message": f"Plugin {plugin_name} is already active"}

        success = await plugin_manager.load_plugin(plugin_name)
        if success:
            return {"message": f"Plugin {plugin_name} activated successfully"}
        else:
            raise HTTPException(status_code=500, detail=f"Failed to activate plugin {plugin_name}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to activate plugin {plugin_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to activate plugin {plugin_name}")


@app.post("/api/plugins/{plugin_name}/deactivate")
async def deactivate_plugin(plugin_name: str):
    """Deactivate a plugin."""
    try:
        if not plugin_manager.lifecycle.is_plugin_active(plugin_name):
            return {"message": f"Plugin {plugin_name} is not active"}

        success = await plugin_manager.unload_plugin(plugin_name)
        if success:
            return {"message": f"Plugin {plugin_name} deactivated successfully"}
        else:
            raise HTTPException(
                status_code=500, detail=f"Failed to deactivate plugin {plugin_name}"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to deactivate plugin {plugin_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to deactivate plugin {plugin_name}")


@app.get("/api/plugins/marketplace")
async def browse_marketplace(
    category: str = None, search: str = None, page: int = 1, limit: int = 20
):
    """Browse available plugins in the marketplace."""
    try:
        result = await plugin_manager.marketplace.list_available_plugins(
            category=category, search=search, limit=limit, offset=(page - 1) * limit
        )
        return result
    except Exception as e:
        logger.error(f"Failed to browse marketplace: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to browse marketplace")


@app.post("/api/plugins/marketplace/install/{plugin_id}")
async def install_plugin_from_marketplace(plugin_id: str, version: str = None):
    """Install a plugin from the marketplace."""
    try:
        success = await plugin_manager.marketplace.install_plugin(plugin_id, version)
        if success:
            return {"message": f"Plugin {plugin_id} installed successfully"}
        else:
            raise HTTPException(status_code=500, detail=f"Failed to install plugin {plugin_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to install plugin {plugin_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to install plugin {plugin_id}")


@app.post("/api/plugins/{plugin_name}/uninstall")
async def uninstall_plugin(plugin_name: str):
    """Uninstall a plugin."""
    try:
        success = await plugin_manager.marketplace.uninstall_plugin(plugin_name)
        if success:
            return {"message": f"Plugin {plugin_name} uninstalled successfully"}
        else:
            raise HTTPException(status_code=500, detail=f"Failed to uninstall plugin {plugin_name}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to uninstall plugin {plugin_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to uninstall plugin {plugin_name}")


@app.post("/api/plugins/{plugin_name}/update")
async def update_plugin(plugin_name: str):
    """Update a plugin to the latest version."""
    try:
        success = await plugin_manager.marketplace.update_plugin(plugin_name)
        if success:
            return {"message": f"Plugin {plugin_name} updated successfully"}
        else:
            raise HTTPException(status_code=500, detail=f"Failed to update plugin {plugin_name}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update plugin {plugin_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update plugin {plugin_name}")


@app.get("/api/plugins/updates")
async def check_plugin_updates():
    """Check for available plugin updates."""
    try:
        updates = await plugin_manager.marketplace.check_for_updates()
        return {"updates": updates}
    except Exception as e:
        logger.error(f"Failed to check for plugin updates: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to check for plugin updates")


@app.get("/plugins", response_class=HTMLResponse)
async def plugin_marketplace_page(request: Request):
    """Plugin marketplace page."""
    return templates.TemplateResponse("plugins.html", {"request": request})


# Role management API endpoints


@app.get("/api/roles")
@require_permission("roles", "view")
async def list_roles(request: Request):
    """Get list of all roles."""
    from .db_managers import db_role_manager

    roles = db_role_manager.list_roles()

    # Convert to API response format
    role_list = []
    for role in roles:
        permissions = db_role_manager.get_role_permissions(role.id)
        role_list.append(
            {
                "id": role.id,
                "name": role.name,
                "description": role.description,
                "permissions": [
                    {"name": p.name, "resource": p.resource, "action": p.action}
                    for p in permissions
                ],
                "created_at": role.created_at.isoformat() if role.created_at else None,
            }
        )

    return {"roles": role_list}


@app.get("/api/roles/{role_id}")
@require_permission("roles", "view")
async def get_role(role_id: str, request: Request):
    """Get details of a specific role."""
    from .db_managers import db_role_manager

    role = db_role_manager.get_role_by_id(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    permissions = db_role_manager.get_role_permissions(role.id)
    return {
        "id": role.id,
        "name": role.name,
        "description": role.description,
        "permissions": [
            {"name": p.name, "resource": p.resource, "action": p.action} for p in permissions
        ],
        "created_at": role.created_at.isoformat() if role.created_at else None,
    }


@app.get("/api/permissions")
@require_permission("roles", "view")
async def list_permissions(request: Request):
    """Get list of all permissions."""
    from .db_managers import db_permission_manager

    permissions = db_permission_manager.list_permissions()

    # Convert to API response format
    permission_list = []
    for permission in permissions:
        permission_list.append(
            {
                "id": permission.id,
                "name": permission.name,
                "resource": permission.resource,
                "action": permission.action,
                "description": permission.description,
                "created_at": permission.created_at.isoformat() if permission.created_at else None,
            }
        )

    return {"permissions": permission_list}


@app.post("/api/roles/{role_id}/permissions")
@require_permission("roles", "manage")
async def assign_permission_to_role(role_id: str, permission_id: str, request: Request):
    """Assign a permission to a role."""
    from .db_managers import db_role_manager

    try:
        db_role_manager.assign_permission_to_role(role_id, permission_id)
        rbac_manager.clear_cache()  # Clear cache after permission changes
        return {"message": "Permission assigned successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/roles/{role_id}/permissions/{permission_id}")
@require_permission("roles", "manage")
async def remove_permission_from_role(role_id: str, permission_id: str, request: Request):
    """Remove a permission from a role."""
    from .db_managers import db_role_manager

    success = db_role_manager.remove_permission_from_role(role_id, permission_id)
    if not success:
        raise HTTPException(status_code=404, detail="Permission assignment not found")

    rbac_manager.clear_cache()  # Clear cache after permission changes
    return {"message": "Permission removed successfully"}


@app.get("/api/users")
@require_permission("users", "view")
async def list_users(request: Request):
    """Get list of all users (admin only)."""
    # This would need to be implemented in the user manager
    # For now, return basic info
    return {"message": "User listing not yet implemented"}


@app.put("/api/users/{user_id}/role")
@require_permission("users", "manage")
async def update_user_role(user_id: str, role_id: str, request: Request):
    """Update a user's role."""
    from .db_managers import db_role_manager, db_user_manager

    # Verify role exists
    role = db_role_manager.get_role_by_id(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    # Update user role
    user = db_user_manager.update_user(user_id, role_id=role_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": "User role updated successfully"}


@app.get("/admin/roles", response_class=HTMLResponse)
@require_permission("roles", "view")
async def role_management_page(request: Request):
    """Role management page."""
    return templates.TemplateResponse("admin/roles.html", {"request": request})


@app.websocket("/ws/conversation")
async def conversation_websocket(websocket: WebSocket):
    """Websocket endpoint for real-time conversation with bidirectional audio streaming.

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
