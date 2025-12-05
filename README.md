# Talk2Me UI

A lightweight, fully offline user interface for the [Talk2Me](https://github.com/FatStinkyPanda/talk2me) voice interaction system. This UI provides comprehensive access to all Talk2Me API endpoints, enabling speech-to-text transcription, text-to-speech synthesis with voice cloning, and advanced audiobook generation with multi-voice support, sound effects, and background audio.

## Table of Contents

- [Features](#features)
- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [User Interface Overview](#user-interface-overview)
- [Voice Management](#voice-management)
- [Speech-to-Text (STT)](#speech-to-text-stt)
- [Text-to-Speech (TTS)](#text-to-speech-tts)
- [Audiobook Generation](#audiobook-generation)
- [Sound Effects System](#sound-effects-system)
- [Background Audio System](#background-audio-system)
- [Audio Configuration](#audio-configuration)
- [Triple Brace Markup Reference](#triple-brace-markup-reference)
- [Configuration](#configuration)
- [API Integration](#api-integration)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)
- [Support](#support)

## Features

### Core Capabilities

- **Fully Offline Operation**: Runs completely locally without internet connectivity
- **Speech-to-Text (STT)**: Real-time audio transcription using Vosk
- **Text-to-Speech (TTS)**: High-quality speech synthesis using XTTS v2
- **Voice Cloning**: Create and manage unlimited custom voice profiles
- **WebSocket Support**: Real-time bidirectional audio streaming
- **Wake Word Detection**: Hands-free voice activation

### Audiobook Generation

- **Multi-Voice Support**: Use multiple cloned voices within a single audiobook
- **Triple Brace Markup**: Simple syntax for voice switching, sound effects, and background audio
- **Sound Effects Integration**: Add and trigger custom sound effects
- **Background Music/Audio**: Ambient audio tracks with configurable behavior
- **Advanced Audio Mixing**: Per-element volume, fade, timing, and playback controls

### Audio Configuration

- **Global Settings**: Default configurations applied to all audio elements
- **Local Overrides**: Per-element customization using inline flags
- **Volume Control**: Independent volume levels for voices, effects, and background audio
- **Fade Effects**: Configurable fade-in and fade-out durations
- **Timing Control**: Start/end timestamps, duration limits, and speech interaction modes

## System Requirements

### Minimum Requirements

- **OS**: Windows 10/11, macOS 10.15+, or Linux (Ubuntu 20.04+)
- **RAM**: 8GB (16GB recommended)
- **Storage**: 5GB available space
- **CPU**: 4-core processor (8-core recommended)
- **Audio**: Microphone and speakers (for interactive features)

### Software Dependencies

- Python 3.9 or higher
- Talk2Me backend server running locally
- Modern web browser (for web-based UI components)

## Installation

### Prerequisites

Ensure the Talk2Me backend is installed and running:

```bash
# Clone and setup Talk2Me backend (if not already installed)
git clone https://github.com/FatStinkyPanda/talk2me.git
cd talk2me
./scripts/setup.sh
```

### Install Talk2Me UI

```bash
# Clone the repository
git clone https://github.com/FatStinkyPanda/talk2me-ui.git
cd talk2me-ui

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Copy example configuration
cp config/config.example.yaml config/config.yaml
```

### Verify Installation

```bash
# Ensure Talk2Me backend is running
curl http://localhost:8000/

# Start Talk2Me UI
python -m talk2me_ui
```

## Quick Start

1. **Start the Talk2Me backend server**:

   ```bash
   cd /path/to/talk2me
   talk2me --api-only --port 8000
   ```

2. **Launch Talk2Me UI**:

   ```bash
   cd /path/to/talk2me-ui
   python -m talk2me_ui
   ```

3. **Open the UI** in your browser at `http://localhost:3000`

4. **Create your first voice clone**:

   - Navigate to Voice Management
   - Click "Create New Voice"
   - Upload 3-5 audio samples of the target voice
   - Name your voice and save

5. **Generate speech**:

   - Go to Text-to-Speech
   - Enter your text
   - Select your cloned voice
   - Click "Generate"

## Deployment

Talk2Me UI supports multiple deployment methods for different environments.

### Development Deployment

#### Using Setup Script (Recommended)

```bash
# Clone the repository
git clone https://github.com/FatStinkyPanda/talk2me-ui.git
cd talk2me-ui

# Run the automated setup
./scripts/setup.sh

# Start development server
./scripts/run_dev.sh
```

The setup script will:

- Check Python version compatibility
- Create a virtual environment
- Install all dependencies
- Set up necessary directories
- Copy default configuration

#### Manual Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy configuration
cp config/example.yaml config/user.yaml

# Start server
uvicorn src.talk2me_ui.main:app --reload --host 0.0.0.0 --port 8000
```

### Production Deployment

#### Using Production Script

```bash
# After setup, run production server
./scripts/run_prod.sh
```

The production script includes:

- Optimized uvicorn settings with multiple workers
- Environment variable loading from `.env.prod`
- Pre-flight checks
- Proper logging configuration

#### Using Docker (Recommended for Production)

```bash
# Build and run with Docker Compose
docker-compose up -d

# Or with nginx reverse proxy
docker-compose --profile with-nginx up -d
```

#### Environment Configuration

Create environment-specific configuration files:

**Development (.env.dev)**:

```bash
APP_ENV=development
LOG_LEVEL=DEBUG
HOST=0.0.0.0
PORT=8000
WORKERS=1
```

**Production (.env.prod)**:

```bash
APP_ENV=production
LOG_LEVEL=INFO
HOST=0.0.0.0
PORT=8000
WORKERS=4
SECRET_KEY=your-secure-secret-key
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
```

### Docker Deployment

#### Basic Docker Setup

```bash
# Build the image
docker build -t talk2me-ui .

# Run the container
docker run -d \
  --name talk2me-ui \
  -p 8000:8000 \
  -v ./data:/app/data \
  -v ./config:/app/config:ro \
  --env-file .env.prod \
  talk2me-ui
```

#### Docker Compose (Recommended)

```yaml
# docker-compose.yml
version: "3.8"
services:
  talk2me-ui:
    build: .
    ports:
      - "8000:8000"
    environment:
      - APP_ENV=production
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    env_file:
      - .env.prod
    restart: unless-stopped
```

#### With Nginx Reverse Proxy

```bash
# Enable nginx profile
docker-compose --profile with-nginx up -d
```

This provides:

- Static file serving optimization
- Gzip compression
- Security headers
- WebSocket proxy support

### Health Checks and Monitoring

#### Health Check Endpoint

The application provides a health check endpoint:

```bash
curl http://localhost:8000/api/health
```

Response:

```json
{
  "status": "healthy",
  "timestamp": "2024-12-05T14:30:00Z",
  "version": "1.0.0",
  "service": "talk2me-ui"
}
```

#### Docker Health Checks

The Docker container includes automatic health checks that monitor the `/api/health` endpoint.

#### Monitoring Setup

For production monitoring, consider:

1. **Application Metrics**: Enable metrics collection
2. **Log Aggregation**: Centralize logs with ELK stack or similar
3. **Container Monitoring**: Use Prometheus + Grafana
4. **Load Balancing**: Distribute traffic across multiple instances

### Deployment Checklist

- [ ] Environment variables configured
- [ ] SSL certificates installed (for HTTPS)
- [ ] Firewall configured
- [ ] Monitoring and alerting set up
- [ ] Backup strategy implemented
- [ ] Domain name configured
- [ ] Load balancer configured (if needed)

## User Interface Overview

### Main Navigation

| Section              | Description                                   |
| -------------------- | --------------------------------------------- |
| **Dashboard**        | System status, quick actions, recent activity |
| **Voice Management** | Create, edit, delete voice profiles           |
| **Speech-to-Text**   | Audio transcription interface                 |
| **Text-to-Speech**   | Single text-to-speech generation              |
| **Audiobook Studio** | Multi-voice audiobook generation              |
| **Sound Library**    | Manage sound effects and background audio     |
| **Settings**         | Global configuration and preferences          |

### Dashboard

The dashboard provides:

- Talk2Me backend connection status
- Available voices count
- Recent generations history
- Quick action buttons for common tasks
- System resource usage (CPU, memory)

## Voice Management

### Creating a Voice Profile

1. Navigate to **Voice Management**
2. Click **"Create New Voice"**
3. Enter voice details:
   - **Name**: Display name for the voice
   - **Language**: Primary language code (e.g., "en", "es", "fr")
   - **Description**: Optional notes about the voice
4. Upload audio samples:
   - Minimum: 3 samples recommended
   - Optimal: 5-10 samples for best quality
   - Format: WAV, 16-bit, mono preferred
   - Duration: 5-30 seconds per sample
   - Quality: Clear recordings without background noise
5. Click **"Create Voice"**

### Voice Sample Guidelines

| Aspect          | Recommendation                   |
| --------------- | -------------------------------- |
| **Format**      | WAV, PCM 16-bit mono             |
| **Sample Rate** | 16000 Hz or 24000 Hz             |
| **Duration**    | 5-30 seconds per sample          |
| **Content**     | Varied sentences, natural speech |
| **Quality**     | Minimal background noise         |
| **Quantity**    | 5-10 samples for optimal cloning |

### Managing Voices

- **Edit Voice**: Update name, language, or add/remove samples
- **Retrain Voice**: Re-process samples after changes
- **Delete Voice**: Remove voice profile and all associated samples
- **Export Voice**: Save voice profile for backup or sharing
- **Import Voice**: Load previously exported voice profiles

## Speech-to-Text (STT)

### Real-Time Transcription

1. Navigate to **Speech-to-Text**
2. Click **"Start Recording"** or use wake word activation
3. Speak clearly into your microphone
4. View real-time transcription results
5. Click **"Stop Recording"** when finished

### File Upload Transcription

1. Click **"Upload Audio File"**
2. Select audio file (WAV format recommended)
3. Click **"Transcribe"**
4. View and copy transcription results

### Supported Audio Formats

- WAV (recommended)
- PCM 16-bit mono
- Sample rates: 8000, 16000, 44100, 48000 Hz

## Text-to-Speech (TTS)

### Basic Generation

1. Navigate to **Text-to-Speech**
2. Enter text in the input field
3. Select a voice from the dropdown
4. Adjust optional settings:
   - Speed
   - Pitch (if supported)
   - Output format
5. Click **"Generate Speech"**
6. Preview and download the generated audio

### Batch Generation

Generate multiple audio files from a list of texts:

1. Click **"Batch Mode"**
2. Enter texts (one per line) or upload a text file
3. Select voice(s) for generation
4. Configure output settings
5. Click **"Generate All"**

## Audiobook Generation

The Audiobook Studio enables creating professional audiobooks with multiple voices, sound effects, and background audio using a simple triple-brace markup system.

### Creating an Audiobook

1. Navigate to **Audiobook Studio**
2. Click **"New Project"**
3. Import your text file or paste content
4. Configure voices, sound effects, and background audio
5. Preview sections as needed
6. Click **"Generate Audiobook"**

### Text File Format

Audiobook text files use triple braces `{{{...}}}` to mark voice changes, sound effects, and background audio:

```
{{{voice:narrator}}}
Once upon a time, in a land far away, there lived a wise old wizard.

{{{voice:wizard}}}
"Come closer, young one. I have much to teach you."

{{{sfx:thunder}}}
{{{bg:rain_ambient}}}

{{{voice:narrator}}}
Thunder rumbled in the distance as rain began to fall.

{{{voice:apprentice}}}
"Master, what is that sound?"

{{{sfx:door_creak,volume:0.8,fade_in:0.5}}}

{{{voice:wizard}}}
"Someone approaches. Stay alert."

{{{bg:stop}}}
```

### Project Settings

| Setting             | Description                      |
| ------------------- | -------------------------------- |
| **Output Format**   | WAV, MP3, or FLAC                |
| **Sample Rate**     | 22050, 24000, or 44100 Hz        |
| **Bit Depth**       | 16-bit or 24-bit                 |
| **Normalization**   | Enable audio level normalization |
| **Chapter Markers** | Generate chapter metadata        |

## Sound Effects System

### Adding Sound Effects

1. Navigate to **Sound Library** > **Sound Effects**
2. Click **"Add Sound Effect"**
3. Upload audio file (WAV, MP3, OGG, FLAC)
4. Configure properties:
   - **ID**: Unique identifier for triple-brace reference
   - **Name**: Display name
   - **Category**: Organization category
   - **Default Volume**: Base volume level (0.0-1.0)
5. Click **"Save"**

### Sound Effect Properties

| Property   | Type   | Description                             |
| ---------- | ------ | --------------------------------------- |
| `id`       | string | Unique identifier used in triple braces |
| `name`     | string | Human-readable display name             |
| `category` | string | Organization category                   |
| `volume`   | float  | Default volume (0.0-1.0)                |
| `fade_in`  | float  | Fade-in duration in seconds             |
| `fade_out` | float  | Fade-out duration in seconds            |
| `start_at` | float  | Start playback at timestamp (seconds)   |
| `end_at`   | float  | End playback at timestamp (seconds)     |
| `duration` | float  | Maximum playback duration               |

### Using Sound Effects in Text

```
{{{sfx:thunder}}}
A loud crack of thunder echoed through the valley.

{{{sfx:footsteps,volume:0.6,fade_in:1.0}}}
The sound of approaching footsteps grew louder.
```

## Background Audio System

### Adding Background Audio

1. Navigate to **Sound Library** > **Background Audio**
2. Click **"Add Background Track"**
3. Upload audio file
4. Configure properties:
   - **ID**: Unique identifier for triple-brace reference
   - **Name**: Display name
   - **Type**: Music, Ambient, or Atmosphere
   - **Loop**: Enable/disable looping
   - **Default Volume**: Base volume level
5. Click **"Save"**

### Background Audio Properties

| Property      | Type    | Description                             |
| ------------- | ------- | --------------------------------------- |
| `id`          | string  | Unique identifier used in triple braces |
| `name`        | string  | Human-readable display name             |
| `type`        | string  | music, ambient, or atmosphere           |
| `volume`      | float   | Default volume (0.0-1.0)                |
| `loop`        | boolean | Loop audio when end is reached          |
| `fade_in`     | float   | Fade-in duration in seconds             |
| `fade_out`    | float   | Fade-out duration in seconds            |
| `duck_speech` | boolean | Lower volume during speech              |
| `duck_level`  | float   | Volume level during ducking (0.0-1.0)   |

### Using Background Audio in Text

```
{{{bg:forest_ambient,volume:0.3,fade_in:2.0}}}
{{{voice:narrator}}}
The forest was alive with the sounds of nature.

{{{bg:dramatic_music,volume:0.4,duck_speech:true,duck_level:0.2}}}
{{{voice:narrator}}}
But danger lurked in the shadows.

{{{bg:stop,fade_out:3.0}}}
Silence fell over the land.
```

## Audio Configuration

### Global Configuration

Global settings apply to all audio elements unless overridden locally.

Navigate to **Settings** > **Audio Configuration** to configure:

```yaml
# Global Audio Settings
audio:
  # Voice Settings
  voice:
    default_volume: 1.0
    normalize: true

  # Sound Effects Settings
  sound_effects:
    default_volume: 0.8
    fade_in: 0.0
    fade_out: 0.0
    pause_speech: false

  # Background Audio Settings
  background:
    default_volume: 0.3
    fade_in: 1.0
    fade_out: 1.0
    duck_speech: true
    duck_level: 0.2
    loop: true
```

### Local Configuration (Per-Element Overrides)

Override global settings for individual elements using inline flags in triple braces:

```
{{{sfx:explosion,volume:1.0,fade_in:0.0,pause_speech:true}}}
```

### Configuration Priority

1. **Local flags** (highest priority) - specified in triple braces
2. **Element defaults** - configured when adding sound/background
3. **Global settings** (lowest priority) - from Settings > Audio Configuration

### Available Configuration Options

#### Sound Effects Flags

| Flag           | Type  | Default | Description                  |
| -------------- | ----- | ------- | ---------------------------- |
| `volume`       | float | 0.8     | Playback volume (0.0-1.0)    |
| `fade_in`      | float | 0.0     | Fade-in duration (seconds)   |
| `fade_out`     | float | 0.0     | Fade-out duration (seconds)  |
| `start_at`     | float | 0.0     | Start playback timestamp     |
| `end_at`       | float | null    | End playback timestamp       |
| `duration`     | float | null    | Maximum duration             |
| `pause_speech` | bool  | false   | Pause speech during playback |

#### Background Audio Flags

| Flag          | Type  | Default | Description                 |
| ------------- | ----- | ------- | --------------------------- |
| `volume`      | float | 0.3     | Playback volume (0.0-1.0)   |
| `fade_in`     | float | 1.0     | Fade-in duration (seconds)  |
| `fade_out`    | float | 1.0     | Fade-out duration (seconds) |
| `loop`        | bool  | true    | Loop audio                  |
| `duck_speech` | bool  | true    | Lower volume during speech  |
| `duck_level`  | float | 0.2     | Volume level during ducking |
| `start_at`    | float | 0.0     | Start playback timestamp    |
| `end_at`      | float | null    | End playback timestamp      |

## Triple Brace Markup Reference

### Syntax Overview

All special elements use triple braces with a type identifier:

```
{{{type:id,flag1:value1,flag2:value2}}}
```

### Voice Changes

```
{{{voice:voice_id}}}
Text spoken by this voice...
```

### Sound Effects

```
{{{sfx:effect_id}}}
{{{sfx:effect_id,volume:0.8,fade_in:0.5}}}
{{{sfx:effect_id,pause_speech:true,duration:3.0}}}
```

### Background Audio

```
{{{bg:track_id}}}
{{{bg:track_id,volume:0.4,fade_in:2.0,loop:true}}}
{{{bg:stop}}}
{{{bg:stop,fade_out:3.0}}}
```

### Complete Example

```
{{{voice:narrator}}}
{{{bg:mysterious_ambient,volume:0.2,fade_in:3.0}}}

Chapter One: The Beginning

The old house stood silent at the edge of town.

{{{sfx:wind_howling,volume:0.6}}}

{{{voice:sarah}}}
"I don't think we should go in there," Sarah whispered.

{{{voice:tom}}}
"Don't be such a coward. It's just an old house."

{{{sfx:door_creak,volume:0.9,pause_speech:true}}}

{{{voice:narrator}}}
The door swung open on its own, revealing only darkness within.

{{{bg:tense_music,volume:0.3,duck_speech:true,duck_level:0.15,fade_in:1.0}}}

{{{voice:sarah}}}
"Tom... did you see that?"

{{{sfx:whisper,volume:0.4,fade_in:0.5,fade_out:1.0}}}

{{{voice:narrator}}}
A faint whisper echoed from somewhere deep inside.

{{{bg:stop,fade_out:2.0}}}
```

## Configuration

### Configuration File

The main configuration file is located at `config/config.yaml`:

```yaml
# Talk2Me UI Configuration

# Backend Connection
backend:
  host: "localhost"
  port: 8000
  timeout: 30
  retry_attempts: 3

# UI Server
server:
  host: "0.0.0.0"
  port: 3000
  debug: false

# Audio Settings
audio:
  voice:
    default_volume: 1.0
    normalize: true
  sound_effects:
    default_volume: 0.8
    fade_in: 0.0
    fade_out: 0.0
    pause_speech: false
  background:
    default_volume: 0.3
    fade_in: 1.0
    fade_out: 1.0
    duck_speech: true
    duck_level: 0.2
    loop: true

# Storage Paths
storage:
  voices: "./data/voices"
  sound_effects: "./data/sfx"
  background_audio: "./data/background"
  projects: "./data/projects"
  exports: "./data/exports"

# Audiobook Generation
audiobook:
  output_format: "wav"
  sample_rate: 24000
  bit_depth: 16
  normalize: true
  chapter_markers: true
```

### Environment Variables

Override configuration using environment variables:

```bash
export TALK2ME_UI_BACKEND_HOST=localhost
export TALK2ME_UI_BACKEND_PORT=8000
export TALK2ME_UI_SERVER_PORT=3000
```

## API Integration

Talk2Me UI communicates with the Talk2Me backend via REST and WebSocket APIs.

### REST Endpoints Used

| Endpoint                           | Method | Purpose                      |
| ---------------------------------- | ------ | ---------------------------- |
| `/`                                | GET    | Health check                 |
| `/stt`                             | POST   | Speech-to-text transcription |
| `/tts`                             | POST   | Text-to-speech synthesis     |
| `/voices`                          | GET    | List available voices        |
| `/voices`                          | POST   | Create new voice             |
| `/voices/{id}`                     | PUT    | Update voice                 |
| `/voices/{id}`                     | DELETE | Delete voice                 |
| `/voices/{id}/samples`             | POST   | Upload voice samples         |
| `/voices/{id}/samples/{sample_id}` | DELETE | Delete voice sample          |
| `/voices/{id}/retrain`             | POST   | Retrain voice model          |

### WebSocket Connection

Real-time audio streaming via WebSocket at `ws://localhost:8000/ws`

### API Client Example

```python
from talk2me_ui.api import Talk2MeClient

client = Talk2MeClient(host="localhost", port=8000)

# List voices
voices = client.list_voices()

# Generate speech
audio = client.synthesize("Hello, world!", voice="my_voice")

# Transcribe audio
text = client.transcribe("recording.wav")
```

## Troubleshooting

### Common Issues

#### Backend Connection Failed

```
Error: Could not connect to Talk2Me backend
```

**Solution**:

1. Verify Talk2Me backend is running: `curl http://localhost:8000/`
2. Check backend host/port in configuration
3. Ensure no firewall blocking the connection

#### Voice Creation Failed

```
Error: Failed to create voice - insufficient samples
```

**Solution**:

1. Upload at least 3 audio samples
2. Ensure samples are in WAV format
3. Check sample duration (5-30 seconds recommended)
4. Verify samples contain clear speech

#### Audio Generation Timeout

```
Error: TTS generation timed out
```

**Solution**:

1. Reduce text length
2. Increase timeout in configuration
3. Check system resources (CPU/RAM usage)
4. Restart Talk2Me backend

#### Sound Effect Not Playing

```
Error: Sound effect 'effect_id' not found
```

**Solution**:

1. Verify the sound effect ID matches exactly
2. Check sound effect exists in Sound Library
3. Ensure audio file is valid and not corrupted

### Logs

View logs for debugging:

```bash
# Talk2Me UI logs
tail -f logs/talk2me_ui.log

# Backend logs (in Talk2Me directory)
tail -f logs/talk2me.log
```

### Performance Optimization

1. **Use SSD storage** for faster audio file access
2. **Increase RAM** for large audiobook projects
3. **Pre-generate** frequently used sound effects
4. **Batch process** multiple chapters
5. **Monitor memory** usage during long generations

## Contributing

We welcome contributions to Talk2Me UI!

### Development Setup

```bash
# Clone repository
git clone https://github.com/FatStinkyPanda/talk2me-ui.git
cd talk2me-ui

# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Run linting
ruff check .

# Run type checking
mypy .
```

### Contribution Guidelines

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Run tests: `pytest`
5. Commit with conventional commits: `git commit -m "feat: add new feature"`
6. Push to your fork: `git push origin feature/my-feature`
7. Open a Pull Request

### Code Style

- Follow PEP 8 guidelines
- Use type hints
- Write docstrings for public functions
- Include unit tests for new features

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/FatStinkyPanda/talk2me-ui/issues)
- **Email**: support@fatstinkypanda.com
- **Documentation**: [Wiki](https://github.com/FatStinkyPanda/talk2me-ui/wiki)

---

**Talk2Me UI** is developed and maintained by **FatStinkyPanda** (Daniel A Bissey).

_Last updated: December 2024_
