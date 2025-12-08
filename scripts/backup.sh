#!/bin/bash
# Talk2Me UI Data Backup Script
# Backs up voice profiles, sound effects, background audio, and projects

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DATA_DIR="$PROJECT_ROOT/data"
BACKUP_DIR="$PROJECT_ROOT/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="talk2me_backup_$TIMESTAMP"
BACKUP_PATH="$BACKUP_DIR/$BACKUP_NAME.tar.gz"

# Default retention settings
DAILY_RETENTION=${DAILY_RETENTION:-7}
WEEKLY_RETENTION=${WEEKLY_RETENTION:-4}
MONTHLY_RETENTION=${MONTHLY_RETENTION:-12}

# Remote storage settings
REMOTE_TYPE=${REMOTE_TYPE:-""}  # "s3", "ftp", "scp"
REMOTE_HOST=${REMOTE_HOST:-""}
REMOTE_USER=${REMOTE_USER:-""}
REMOTE_PATH=${REMOTE_PATH:-""}
S3_BUCKET=${S3_BUCKET:-""}
S3_REGION=${S3_REGION:-"us-east-1"}

# Logging
LOG_FILE="$PROJECT_ROOT/logs/backup.log"
mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

error() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $*" >&2 | tee -a "$LOG_FILE"
    exit 1
}

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Check if data directory exists
if [[ ! -d "$DATA_DIR" ]]; then
    error "Data directory $DATA_DIR does not exist"
fi

log "Starting backup of Talk2Me UI data"
log "Backup name: $BACKUP_NAME"
log "Data directory: $DATA_DIR"
log "Backup location: $BACKUP_PATH"

# Create temporary directory for backup staging
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

# Copy data to temp directory (only include directories that exist)
if [[ -d "$DATA_DIR/voices" ]]; then
    cp -r "$DATA_DIR/voices" "$TEMP_DIR/"
    log "Included voices directory"
fi

if [[ -d "$DATA_DIR/sfx" ]]; then
    cp -r "$DATA_DIR/sfx" "$TEMP_DIR/"
    log "Included sound effects directory"
fi

if [[ -d "$DATA_DIR/background" ]]; then
    cp -r "$DATA_DIR/background" "$TEMP_DIR/"
    log "Included background audio directory"
fi

if [[ -d "$DATA_DIR/projects" ]]; then
    cp -r "$DATA_DIR/projects" "$TEMP_DIR/"
    log "Included projects directory"
fi

if [[ -d "$DATA_DIR/exports" ]]; then
    cp -r "$DATA_DIR/exports" "$TEMP_DIR/"
    log "Included exports directory"
fi

# Create backup manifest
cat > "$TEMP_DIR/backup_manifest.txt" << EOF
Talk2Me UI Data Backup
Created: $(date)
Backup Name: $BACKUP_NAME
Contents:
$(ls -la "$TEMP_DIR")
EOF

# Create compressed archive
log "Creating compressed backup archive..."
tar -czf "$BACKUP_PATH" -C "$TEMP_DIR" .

# Get backup size
BACKUP_SIZE=$(du -h "$BACKUP_PATH" | cut -f1)
log "Backup created successfully. Size: $BACKUP_SIZE"

# Upload to remote storage if configured
upload_to_remote() {
    case "$REMOTE_TYPE" in
        "s3")
            if [[ -n "$S3_BUCKET" ]]; then
                log "Uploading to S3 bucket: $S3_BUCKET"
                aws s3 cp "$BACKUP_PATH" "s3://$S3_BUCKET/$BACKUP_NAME.tar.gz" --region "$S3_REGION"
                log "Upload to S3 completed"
            fi
            ;;
        "scp")
            if [[ -n "$REMOTE_HOST" && -n "$REMOTE_USER" && -n "$REMOTE_PATH" ]]; then
                log "Uploading via SCP to $REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH"
                scp "$BACKUP_PATH" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/"
                log "SCP upload completed"
            fi
            ;;
        "ftp")
            if [[ -n "$REMOTE_HOST" && -n "$REMOTE_USER" && -n "$REMOTE_PATH" ]]; then
                log "Uploading via FTP to $REMOTE_HOST:$REMOTE_PATH"
                curl -T "$BACKUP_PATH" "ftp://$REMOTE_USER@$REMOTE_HOST$REMOTE_PATH/$BACKUP_NAME.tar.gz"
                log "FTP upload completed"
            fi
            ;;
        *)
            log "No remote storage configured or unsupported type: $REMOTE_TYPE"
            ;;
    esac
}

upload_to_remote

# Clean up old backups
cleanup_old_backups() {
    log "Cleaning up old backups (daily: $DAILY_RETENTION, weekly: $WEEKLY_RETENTION, monthly: $MONTHLY_RETENTION)"

    # Daily backups (keep last N)
    find "$BACKUP_DIR" -name "talk2me_backup_*.tar.gz" -type f -printf '%T@ %p\n' | \
        sort -n | head -n -"$DAILY_RETENTION" | cut -d' ' -f2- | xargs -r rm -f

    # Weekly backups (keep last N Sundays)
    find "$BACKUP_DIR" -name "talk2me_backup_*.tar.gz" -type f | \
        grep -E "_[0-9]{8}_[0-9]{6}\.tar\.gz$" | \
        sed 's/.*talk2me_backup_\([0-9]\{8\}\)_[0-9]\{6\}\.tar\.gz/\1/' | \
        date -f - +%w 2>/dev/null | \
        paste - <(find "$BACKUP_DIR" -name "talk2me_backup_*.tar.gz" -type f) | \
        awk '$1 == 0 {print $2}' | \
        sort | head -n -"$WEEKLY_RETENTION" | \
        xargs -r rm -f

    # Monthly backups (keep last N of the 1st of each month)
    find "$BACKUP_DIR" -name "talk2me_backup_*.tar.gz" -type f | \
        grep -E "_[0-9]{8}_[0-9]{6}\.tar\.gz$" | \
        sed 's/.*talk2me_backup_\([0-9]\{8\}\)_[0-9]\{6\}\.tar\.gz/\1/' | \
        date -f - +%d 2>/dev/null | \
        paste - <(find "$BACKUP_DIR" -name "talk2me_backup_*.tar.gz" -type f) | \
        awk '$1 == "01" {print $2}' | \
        sort | head -n -"$MONTHLY_RETENTION" | \
        xargs -r rm -f

    log "Cleanup completed"
}

cleanup_old_backups

log "Backup process completed successfully"
log "Backup saved to: $BACKUP_PATH"

# Print summary
echo "========================================"
echo "Talk2Me UI Backup Summary"
echo "========================================"
echo "Backup Name: $BACKUP_NAME"
echo "Created: $(date)"
echo "Size: $BACKUP_SIZE"
echo "Location: $BACKUP_PATH"
if [[ -n "$REMOTE_TYPE" ]]; then
    echo "Remote Storage: $REMOTE_TYPE"
fi
echo "========================================"
