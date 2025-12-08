# Talk2Me UI

A lightweight, fully offline user interface for the [Talk2Me](https://github.com/FatStinkyPanda/talk2me) voice interaction system. This UI provides comprehensive access to all Talk2Me API endpoints, enabling speech-to-text transcription, text-to-speech synthesis with voice cloning, and advanced audiobook generation with multi-voice support, sound effects, and background audio.

## Table of Contents

- [Features](#features)
- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [User Authentication](#user-authentication)
- [User Interface Overview](#user-interface-overview)
- [Voice Management](#voice-management)
- [Speech-to-Text (STT)](#speech-to-text-stt)
- [Text-to-Speech (TTS)](#text-to-speech-tts)
- [Audiobook Generation](#audiobook-generation)
- [Sound Effects System](#sound-effects-system)
- [Background Audio System](#background-audio-system)
- [Audio Configuration](#audio-configuration)
- [Plugin System](#plugin-system)
- [Triple Brace Markup Reference](#triple-brace-markup-reference)
- [Configuration](#configuration)
- [API Integration](#api-integration)
- [Troubleshooting](#troubleshooting)
- [Data Backup and Recovery](#data-backup-and-recovery)
- [Contributing](#contributing)
- [License](#license)
- [Support](#support)

## Features

### Core Capabilities

- **Fully Offline Operation**: Runs completely locally without internet connectivity
- **User Authentication**: Secure user registration, login, and session management
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

### Plugin System

- **Extensible Architecture**: Third-party developers can add custom functionality
- **Audio Processors**: Custom audio processing plugins for effects, normalization, etc.
- **UI Components**: Extend the web interface with custom components and pages
- **API Endpoints**: Add new REST API endpoints for custom functionality
- **Integrations**: Connect to external services and APIs
- **Plugin Marketplace**: Browse and install plugins from a central repository
- **Lifecycle Management**: Activate, deactivate, and update plugins dynamically

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

4. **Register or login** to access the application features

5. **Create your first voice clone**:
   - Navigate to Voice Management
   - Click "Create New Voice"
   - Upload 3-5 audio samples of the target voice
   - Name your voice and save

6. **Generate speech**:
   - Go to Text-to-Speech
   - Enter your text
   - Select your cloned voice
   - Click "Generate"

## User Authentication

Talk2Me UI includes a comprehensive user authentication system with secure session management, password hashing, and protected routes.

### User Registration

1. **Access Registration**: Navigate to `/auth/register` or click "Register" on the login page
2. **Enter Details**:
   - **Username**: 3-50 characters, letters, numbers, underscores, and hyphens only
   - **Email**: Valid email address
   - **Password**: Minimum 8 characters
   - **Confirm Password**: Must match password
3. **Submit**: Click "Register" to create your account
4. **Login**: After successful registration, you'll be redirected to login

### User Login

1. **Access Login**: Navigate to `/auth/login` or visit the root URL (redirects to login if not authenticated)
2. **Enter Credentials**:
   - **Username or Email**: Your registered username or email address
   - **Password**: Your account password
3. **Submit**: Click "Login" to authenticate
4. **Session**: Upon successful login, you'll be redirected to the dashboard with an active session

### Session Management

- **Secure Cookies**: Session data is stored in secure, HTTP-only cookies
- **Session Timeout**: Sessions automatically expire after 24 hours of inactivity
- **Automatic Logout**: Users are automatically logged out when sessions expire
- **Concurrent Sessions**: Multiple active sessions per user are supported

### Security Features

- **Password Hashing**: Passwords are hashed using bcrypt with salt
- **CSRF Protection**: All forms include CSRF tokens for protection
- **Session Security**: Sessions include IP address and user agent tracking
- **Route Protection**: All application routes require authentication
- **Secure Headers**: Additional security headers are applied to all responses

### Password Requirements

- Minimum 8 characters
- No specific complexity requirements (but recommended to use strong passwords)
- Passwords are never stored in plain text

### Account Management

Currently, account management features include:

- User registration and login
- Session management and logout
- Password security (hashing and verification)

### Role-Based Access Control (RBAC)

Talk2Me UI implements comprehensive role-based access control with predefined roles and granular permissions:

#### Default Roles

| Role      | Description               | Permissions                                                                           |
| --------- | ------------------------- | ------------------------------------------------------------------------------------- |
| **admin** | Full system administrator | All permissions including user management, system administration, and role management |
| **user**  | Regular user              | Basic functionality: STT, TTS, audiobook generation, voice/sound management           |
| **guest** | Limited access user       | Read-only access to basic features, limited TTS/STT capabilities                      |

#### Permission Categories

- **STT**: Speech-to-text functionality
- **TTS**: Text-to-speech functionality
- **Audiobook**: Audiobook generation and management
- **Voices**: Voice profile management
- **Sounds**: Sound effects and background audio management
- **Users**: User account management
- **Roles**: Role and permission management
- **Plugins**: Plugin installation and management
- **System**: System administration and monitoring

#### Role Management

Administrators can manage roles and permissions through the web interface:

1. Navigate to **Role Management** (admin only)
2. View existing roles and their permissions
3. Assign or remove permissions from roles
4. Create custom roles if needed

#### Permission Enforcement

Permissions are enforced at multiple levels:

- **API Endpoints**: Protected routes check user permissions before execution
- **UI Elements**: Interface elements are shown/hidden based on user permissions
- **Database Operations**: Data access is restricted based on user roles

Future enhancements may include:

- Password reset functionality
- Account profile management
- Custom role creation
- Permission auditing and logging

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

#### With SSL/HTTPS (Production)

For production deployments with SSL certificates:

1. **Set Domain Environment Variable**:

   ```bash
   export DOMAIN=yourdomain.com
   ```

2. **Update nginx.conf** (optional):

   Replace `server_name localhost;` with your domain:

   ```nginx
   server_name yourdomain.com www.yourdomain.com;
   ```

3. **Run with SSL Support**:

   ```bash
   # Start with nginx and SSL
   docker-compose --profile with-nginx up -d

   # The certbot service will automatically:
   # - Obtain SSL certificate from Let's Encrypt
   # - Configure nginx for HTTPS
   # - Set up automatic certificate renewal
   ```

4. **SSL Features**:
   - **Automatic Certificate Management**: Let's Encrypt integration
   - **HTTPS Termination**: SSL handled by nginx
   - **Security Headers**: HSTS, CSP, X-Frame-Options
   - **Certificate Renewal**: Automatic renewal every 12 hours
   - **HTTP to HTTPS Redirect**: All HTTP traffic redirected to HTTPS

5. **Production Checklist**:
   - [ ] Domain DNS configured to point to server
   - [ ] Port 80 and 443 open in firewall
   - [ ] DOMAIN environment variable set
   - [ ] nginx.conf updated with correct server_name
   - [ ] SSL certificates obtained (automatic)
   - [ ] HTTPS working (test with curl -I https://yourdomain.com)

6. **Troubleshooting SSL**:
   - **Certificate Not Obtained**: Check DOMAIN env var and DNS
   - **nginx SSL Errors**: Verify certificate files exist in /etc/letsencrypt/live/
   - **Renewal Issues**: Check certbot logs in container
   - **Port Issues**: Ensure ports 80/443 are accessible from internet

   ```bash
   # Check certificate status
   docker-compose exec certbot certbot certificates

   # Manual renewal test
   docker-compose exec certbot certbot renew --dry-run
   ```

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

Talk2Me UI includes built-in Prometheus metrics and Grafana dashboards for comprehensive monitoring.

##### Prometheus Metrics

The application exposes Prometheus metrics at `/metrics` endpoint:

- **HTTP Request Metrics**: Request count, duration, and error rates by endpoint
- **Audio Processing Metrics**: Task counts and processing durations for STT, TTS, and audiobook generation
- **System Health**: Application uptime and health status

##### Grafana Dashboards

Pre-configured dashboards include:

- HTTP request rate and latency graphs
- Audio processing task success rates
- System resource usage trends
- Error rate monitoring

##### Starting Monitoring Stack

```bash
# Start with monitoring enabled
docker-compose --profile with-monitoring up -d

# Access points:
# - Talk2Me UI: http://localhost:8000
# - Prometheus: http://localhost:9090
# - Grafana: http://localhost:3000 (admin/admin)
```

##### Dashboard Access

1. Open Grafana at `http://localhost:3000`
2. Login with `admin` / `admin`
3. Navigate to "Talk2Me UI Monitoring" dashboard
4. View real-time metrics and performance data

##### Custom Metrics

The metrics system tracks:

- API endpoint performance
- Audio processing success/failure rates
- Request latency percentiles (50th, 95th, 99th)
- Task queue status and processing times

For production monitoring, consider:

1. **Application Metrics**: Enable metrics collection (built-in)
2. **Log Aggregation**: Centralize logs with ELK stack or similar
3. **Container Monitoring**: Use Prometheus + Grafana (included)
4. **Load Balancing**: Distribute traffic across multiple instances

### Deployment Checklist

- [ ] Environment variables configured
- [ ] Domain name configured and DNS pointing to server
- [ ] SSL certificates obtained (automatic with Let's Encrypt)
- [ ] HTTPS working (test with curl -I https://yourdomain.com)
- [ ] Firewall configured (ports 80, 443 open)
- [ ] Monitoring and alerting set up
- [ ] Backup strategy implemented
- [ ] Load balancer configured (if needed)

## Data Backup and Recovery

Talk2Me UI includes comprehensive automated backup and recovery capabilities for all user data including voice profiles, sound effects, background audio, and projects.

### Backup Components

The backup system consists of:

- **Automated Backup Service**: Docker container running scheduled backups
- **Backup Scripts**: Command-line tools for manual backup/restore operations
- **Retention Policies**: Configurable cleanup of old backups
- **Remote Storage Support**: S3, FTP, and SCP upload capabilities

### What Gets Backed Up

| Component            | Location           | Description                            |
| -------------------- | ------------------ | -------------------------------------- |
| **Voice Profiles**   | `data/voices/`     | Voice cloning data and metadata        |
| **Sound Effects**    | `data/sfx/`        | Audio files and configuration metadata |
| **Background Audio** | `data/background/` | Ambient audio tracks and settings      |
| **Projects**         | `data/projects/`   | Audiobook projects and configurations  |
| **Exports**          | `data/exports/`    | Generated audio exports (optional)     |

### Automated Backup Setup

#### Using Docker Compose (Recommended)

Enable automated backups by running with the backup profile:

```bash
# Start with automated backups
docker-compose --profile with-backup up -d

# Or combine with other services
docker-compose --profile with-backup --profile with-monitoring up -d
```

The backup service will:

- Run daily backups at 2:00 AM
- Store backups locally in `./backups/`
- Apply retention policies automatically
- Upload to remote storage if configured

#### Backup Configuration

Configure backup settings using environment variables:

```bash
# Retention settings
DAILY_RETENTION=7      # Keep 7 daily backups
WEEKLY_RETENTION=4     # Keep 4 weekly backups
MONTHLY_RETENTION=12   # Keep 12 monthly backups

# Remote storage (optional)
BACKUP_REMOTE_TYPE=s3          # s3, ftp, or scp
BACKUP_REMOTE_HOST=ftp.example.com
BACKUP_REMOTE_USER=username
BACKUP_REMOTE_PATH=/backups/
BACKUP_S3_BUCKET=my-backups
BACKUP_S3_REGION=us-east-1
```

### Manual Backup Operations

#### Creating a Backup

```bash
# Create a backup manually
./scripts/backup.sh

# Backup with custom settings
REMOTE_TYPE=s3 S3_BUCKET=my-bucket ./scripts/backup.sh
```

#### Listing Available Backups

```bash
# List all available backups
./scripts/restore.sh --list
```

#### Restoring from Backup

```bash
# Dry run to see what would be restored
./scripts/restore.sh --dry-run latest

# Restore latest backup
./scripts/restore.sh latest

# Restore specific backup
./scripts/restore.sh backups/talk2me_backup_20231201_120000.tar.gz

# Restore only specific components
RESTORE_VOICES=1 RESTORE_SFX=0 ./scripts/restore.sh latest
```

### Backup File Format

Backups are compressed tar.gz archives with the naming convention:

```
talk2me_backup_YYYYMMDD_HHMMSS.tar.gz
```

Each backup contains:

- Complete data directories
- Backup manifest with creation details
- File integrity information

### Retention Policy

The system automatically manages backup retention:

| Backup Type | Retention | Schedule             |
| ----------- | --------- | -------------------- |
| **Daily**   | 7 days    | Every day at 2:00 AM |
| **Weekly**  | 4 weeks   | Every Sunday         |
| **Monthly** | 12 months | 1st of each month    |

Old backups are automatically deleted when new ones are created.

### Remote Storage Options

#### Amazon S3

```bash
export BACKUP_REMOTE_TYPE=s3
export BACKUP_S3_BUCKET=my-talk2me-backups
export BACKUP_S3_REGION=us-east-1
# AWS credentials via AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY
```

#### FTP Server

```bash
export BACKUP_REMOTE_TYPE=ftp
export BACKUP_REMOTE_HOST=ftp.example.com
export BACKUP_REMOTE_USER=myuser
export BACKUP_REMOTE_PATH=/backups/talk2me/
```

#### SCP/SFTP

```bash
export BACKUP_REMOTE_TYPE=scp
export BACKUP_REMOTE_HOST=server.example.com
export BACKUP_REMOTE_USER=myuser
export BACKUP_REMOTE_PATH=/home/myuser/backups/
# SSH key authentication supported
```

### Recovery Procedures

#### Emergency Recovery

If the main data directory is lost or corrupted:

1. **Stop the application**:

   ```bash
   docker-compose down
   ```

2. **Restore from backup**:

   ```bash
   ./scripts/restore.sh latest
   ```

3. **Verify restoration**:

   ```bash
   ls -la data/
   ```

4. **Restart the application**:
   ```bash
   docker-compose up -d
   ```

#### Partial Recovery

Restore only specific components:

```bash
# Restore only voices and sound effects
RESTORE_VOICES=1 RESTORE_SFX=1 RESTORE_BACKGROUND=0 RESTORE_PROJECTS=0 ./scripts/restore.sh latest
```

#### Point-in-Time Recovery

```bash
# List available backups
./scripts/restore.sh --list

# Restore specific backup by date/time
./scripts/restore.sh backups/talk2me_backup_20231201_120000.tar.gz
```

### Backup Monitoring

Monitor backup operations through logs:

```bash
# View backup logs
tail -f logs/backup.log

# Check backup service status
docker-compose ps backup

# View backup service logs
docker-compose logs backup
```

### Best Practices

#### Backup Strategy

1. **Test Restorations**: Regularly test backup restoration procedures
2. **Multiple Locations**: Use both local and remote storage
3. **Monitor Space**: Ensure adequate storage for backup retention
4. **Verify Integrity**: Check backup logs for successful completion
5. **Document Procedures**: Keep recovery procedures documented and accessible

#### Storage Requirements

- **Local Storage**: Minimum 2x data size for backup directory
- **Remote Storage**: Depends on retention policy and data growth
- **Network**: Stable connection required for remote uploads

#### Security Considerations

- **Encryption**: Backups contain sensitive audio data
- **Access Control**: Limit access to backup storage locations
- **Remote Credentials**: Use secure methods for remote storage authentication
- **Network Security**: Use encrypted connections (SFTP/SCP over FTP)

### Troubleshooting Backups

#### Backup Fails

```
Error: Permission denied creating backup directory
```

**Solution**:

```bash
sudo chown -R $USER:$USER ./backups
chmod 755 ./backups
```

#### Remote Upload Fails

```
Error: Failed to upload to remote storage
```

**Solutions**:

- Verify credentials and permissions
- Check network connectivity
- Confirm remote storage configuration
- Review backup service logs

#### Insufficient Space

```
Error: No space left on device
```

**Solutions**:

- Clean old backups manually
- Increase retention settings
- Add more storage space
- Move backups to external storage

#### Restore Fails

```
Error: Backup file corrupted
```

**Solutions**:

- Try a different backup file
- Check file integrity: `tar -tzf backup.tar.gz`
- Restore from remote storage if available
- Contact support if all backups are corrupted

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

## Plugin System

Talk2Me UI includes a comprehensive plugin architecture that allows third-party developers to extend the application's functionality without modifying the core codebase.

### Plugin Types

#### Audio Processor Plugins

Extend audio processing capabilities with custom effects, filters, and transformations:

- **Noise Reduction**: Remove background noise from audio
- **Equalization**: Apply frequency-specific adjustments
- **Compression**: Dynamic range compression
- **Reverb/Echo**: Add spatial audio effects
- **Normalization**: Automatic volume leveling

#### UI Component Plugins

Add new user interface elements and pages:

- **Dashboard Widgets**: Custom monitoring and control panels
- **Audio Editors**: Specialized audio editing interfaces
- **Visualization Tools**: Real-time audio waveform displays
- **Settings Panels**: Custom configuration interfaces

#### API Endpoint Plugins

Extend the REST API with new functionality:

- **Data Export**: Custom export formats and destinations
- **Batch Processing**: Bulk audio processing operations
- **Integration APIs**: Third-party service connections
- **Analytics**: Usage statistics and reporting

#### Integration Plugins

Connect Talk2Me UI to external services:

- **Cloud Storage**: Upload to AWS S3, Google Drive, Dropbox
- **Social Media**: Share audio to Twitter, YouTube, TikTok
- **Webhooks**: Real-time notifications to external systems
- **Database**: Store metadata in external databases

### Plugin Management

#### Installing Plugins

Plugins can be installed from the built-in marketplace or manually:

```bash
# Access the plugin marketplace
# Navigate to /plugins in your browser

# Or install via API
curl -X POST /api/plugins/marketplace/install/audio_enhancer
```

#### Managing Plugins

- **Activate/Deactivate**: Enable or disable plugins without uninstalling
- **Update**: Install newer versions of installed plugins
- **Configure**: Adjust plugin settings through the web interface
- **Monitor**: View plugin status and performance metrics

#### Plugin Marketplace

Browse and install plugins from a curated repository:

- **Search**: Find plugins by name, category, or functionality
- **Categories**: Filter by audio processing, UI, API, or integrations
- **Ratings**: Community-rated plugins with reviews
- **Updates**: Automatic notifications for plugin updates

### Developing Plugins

#### Plugin Structure

```
my_plugin/
├── plugin.json      # Plugin metadata and configuration
├── plugin.py        # Main plugin implementation
├── static/          # Static assets (CSS, JS, images)
├── templates/       # Jinja2 templates
└── README.md        # Plugin documentation
```

#### plugin.json Example

```json
{
  "name": "audio_enhancer",
  "version": "1.0.0",
  "description": "Advanced audio enhancement with noise reduction",
  "author": "Audio Labs Inc",
  "type": "audio_processor",
  "dependencies": [],
  "config_schema": {
    "type": "object",
    "properties": {
      "noise_reduction": {
        "type": "boolean",
        "default": true,
        "description": "Enable noise reduction"
      },
      "enhancement_level": {
        "type": "number",
        "default": 0.5,
        "minimum": 0.0,
        "maximum": 1.0,
        "description": "Enhancement intensity"
      }
    }
  },
  "homepage": "https://github.com/audiolabs/audio-enhancer",
  "license": "MIT"
}
```

#### Plugin Implementation Example

```python
from src.talk2me_ui.plugins.interfaces import AudioProcessorPlugin, PluginMetadata

class AudioEnhancer(AudioProcessorPlugin):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="audio_enhancer",
            version="1.0.0",
            description="Advanced audio enhancement",
            author="Audio Labs Inc",
            plugin_type="audio_processor",
        )

    async def initialize(self, config: Dict[str, Any]) -> None:
        self.noise_reduction = config.get("noise_reduction", True)
        self.enhancement_level = config.get("enhancement_level", 0.5)

    async def shutdown(self) -> None:
        # Cleanup resources
        pass

    async def process_audio(self, audio: AudioSegment, config: Dict[str, Any]) -> AudioSegment:
        # Apply audio enhancement
        enhanced = audio

        if self.noise_reduction:
            enhanced = self._reduce_noise(enhanced)

        enhanced = self._enhance_audio(enhanced, self.enhancement_level)

        return enhanced

    def _reduce_noise(self, audio: AudioSegment) -> AudioSegment:
        # Implement noise reduction algorithm
        return audio

    def _enhance_audio(self, audio: AudioSegment, level: float) -> AudioSegment:
        # Implement audio enhancement
        return audio
```

#### Publishing Plugins

1. **Test Thoroughly**: Ensure your plugin works correctly
2. **Document**: Provide clear documentation and examples
3. **Package**: Create a proper plugin directory structure
4. **Submit**: Submit to the plugin marketplace for review

### Security Considerations

- Plugins run with the same permissions as the main application
- Always review plugin code before installation
- Use sandboxing for untrusted plugins in production environments
- Regularly update plugins to address security issues

For detailed plugin development documentation, see [`src/talk2me_ui/plugins/README.md`](src/talk2me_ui/plugins/README.md).

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

### Environment Variable Configuration

Talk2Me UI uses environment variables for runtime configuration. This section covers setup, validation, and best practices.

#### Environment Files

Create environment-specific configuration files:

- **Development**: `.env.dev`
- **Production**: `.env.prod`
- **Template**: `.env.example` (comprehensive template with all variables)

Copy the template and customize for your environment:

```bash
# Copy the template
cp .env.example .env.dev

# Edit with your settings
nano .env.dev
```

#### Required Environment Variables

| Variable    | Development Default | Production Required | Description              |
| ----------- | ------------------- | ------------------- | ------------------------ |
| `APP_ENV`   | `development`       | `production`        | Application environment  |
| `LOG_LEVEL` | `DEBUG`             | `INFO`              | Logging verbosity level  |
| `DEBUG`     | `true`              | `false`             | Enable debug mode        |
| `HOST`      | `0.0.0.0`           | `0.0.0.0`           | Server bind address      |
| `PORT`      | `8000`              | `8000`              | Server port              |
| `WORKERS`   | `1`                 | `4`                 | Number of server workers |

#### Security Variables (Production Critical)

| Variable         | Description               | Requirements                       |
| ---------------- | ------------------------- | ---------------------------------- |
| `SECRET_KEY`     | Session encryption key    | 32+ characters, randomly generated |
| `SESSION_SECRET` | Session management secret | 32+ characters, randomly generated |

**Generate secure secrets:**

```bash
# Generate SECRET_KEY
python3 -c "import secrets; print(secrets.token_hex(32))"

# Generate SESSION_SECRET
python3 -c "import secrets; print(secrets.token_hex(32))"
```

#### Optional Environment Variables

| Variable           | Default                                       | Description                       |
| ------------------ | --------------------------------------------- | --------------------------------- |
| `ALLOWED_HOSTS`    | `localhost,127.0.0.1`                         | Comma-separated allowed hostnames |
| `MAX_FILE_SIZE`    | `52428800`                                    | Maximum upload file size (bytes)  |
| `UPLOAD_DIR`       | `data/uploads`                                | File upload directory             |
| `CORS_ORIGINS`     | `http://localhost:3000,http://localhost:8000` | Allowed CORS origins              |
| `ENABLE_METRICS`   | `false`                                       | Enable Prometheus metrics         |
| `METRICS_PORT`     | `9090`                                        | Metrics server port               |
| `LOG_FILE`         | -                                             | Optional log file path            |
| `LOG_MAX_SIZE`     | `10485760`                                    | Max log file size (bytes)         |
| `LOG_BACKUP_COUNT` | `5`                                           | Number of log backup files        |

#### SSL/TLS Configuration

For HTTPS deployments:

| Variable        | Description               | Example                                              |
| --------------- | ------------------------- | ---------------------------------------------------- |
| `SSL_CERT_PATH` | SSL certificate file path | `/etc/letsencrypt/live/yourdomain.com/fullchain.pem` |
| `SSL_KEY_PATH`  | SSL private key file path | `/etc/letsencrypt/live/yourdomain.com/privkey.pem`   |
| `DOMAIN`        | Domain name for SSL       | `yourdomain.com`                                     |

#### Backup Configuration

| Variable             | Description             | Example              |
| -------------------- | ----------------------- | -------------------- |
| `BACKUP_REMOTE_TYPE` | Remote storage type     | `s3`, `scp`, `ftp`   |
| `BACKUP_REMOTE_HOST` | Remote backup host      | `backup.example.com` |
| `BACKUP_REMOTE_USER` | Remote backup username  | `backupuser`         |
| `BACKUP_REMOTE_PATH` | Remote backup path      | `/backups`           |
| `BACKUP_S3_BUCKET`   | S3 bucket name          | `my-backups`         |
| `BACKUP_S3_REGION`   | AWS S3 region           | `us-east-1`          |
| `DAILY_RETENTION`    | Daily backups to keep   | `7`                  |
| `WEEKLY_RETENTION`   | Weekly backups to keep  | `4`                  |
| `MONTHLY_RETENTION`  | Monthly backups to keep | `12`                 |

#### Environment Variable Validation

Talk2Me UI automatically validates environment variables at startup:

**Validation Checks:**

- Required variables present for environment
- Security variables meet minimum requirements
- Port numbers in valid range (1-65535)
- Worker count reasonable (>0, <100)
- File sizes within limits
- Paths are absolute when required
- Boolean values are valid

**Validation Output:**

```
🔍 Environment Validation Results:
Environment: production
Issues found: 2
  ⚠️  Required variable 'SECRET_KEY' is not set
  ⚠️  Security variable 'SESSION_SECRET' contains default/placeholder value - change immediately
```

**Critical Issues:**

- Missing required variables
- Insecure security values
- Invalid port/worker configurations

**Non-Critical Issues:**

- Missing optional variables
- Suboptimal configurations
- Performance warnings

#### Environment Setup Procedures

##### Development Setup

1. **Copy template:**

   ```bash
   cp .env.example .env.dev
   ```

2. **Configure basic settings:**

   ```bash
   # .env.dev
   APP_ENV=development
   LOG_LEVEL=DEBUG
   DEBUG=true
   HOST=0.0.0.0
   PORT=8000
   WORKERS=1
   ```

3. **Start development server:**
   ```bash
   ./scripts/run_dev.sh
   ```

##### Production Setup

1. **Copy and secure template:**

   ```bash
   cp .env.example .env.prod
   chmod 600 .env.prod
   ```

2. **Configure production settings:**

   ```bash
   # .env.prod
   APP_ENV=production
   LOG_LEVEL=INFO
   DEBUG=false
   HOST=0.0.0.0
   PORT=8000
   WORKERS=4

   # Generate and set secure secrets
   SECRET_KEY=your-generated-32-char-secret-key
   SESSION_SECRET=your-generated-32-char-session-secret

   # Domain and SSL
   DOMAIN=yourdomain.com
   ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
   CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

   # Enable monitoring
   ENABLE_METRICS=true
   METRICS_PORT=9090
   ```

3. **Validate configuration:**

   ```bash
   python3 -c "
   import os
   os.environ['APP_ENV'] = 'production'
   # Load your .env.prod here
   from talk2me_ui.validation import EnvironmentValidator
   summary = EnvironmentValidator.get_validation_summary()
   print(f'Valid: {summary[\"is_valid\"]}')
   for issue in summary['issues']:
       print(f'  - {issue}')
   "
   ```

4. **Start production server:**
   ```bash
   ./scripts/run_prod.sh
   ```

#### Security Best Practices

1. **Never commit .env files** to version control
2. **Use strong, randomly generated secrets** for security variables
3. **Restrict ALLOWED_HOSTS** to your actual domains in production
4. **Set DEBUG=false** in production environments
5. **Use HTTPS** with valid SSL certificates
6. **Regularly rotate** SECRET_KEY and SESSION_SECRET
7. **Limit CORS_ORIGINS** to trusted domains only

#### Troubleshooting Environment Issues

**Validation fails on startup:**

```bash
# Check current environment
env | grep -E "(APP_ENV|SECRET_KEY|SESSION_SECRET|HOST|PORT)"

# Run validation manually
python3 -c "
from talk2me_ui.validation import EnvironmentValidator
summary = EnvironmentValidator.get_validation_summary()
print(f'Issues: {len(summary[\"issues\"])}')
for issue in summary['issues']:
    print(f'  - {issue}')
"
```

**Application won't start:**

- Verify all required variables are set
- Check variable values are valid (ports, booleans, etc.)
- Ensure .env file permissions are correct (readable by app user)
- Check for typos in variable names

**Security warnings:**

- Generate new secrets using the provided commands
- Never use default placeholder values in production
- Use a password manager to store secrets securely

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

### Legacy Environment Variables

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

_Last updated: December 2025_
