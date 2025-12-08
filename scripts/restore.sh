#!/bin/bash
# Talk2Me UI Data Restore Script
# Restores data from backup archives

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DATA_DIR="$PROJECT_ROOT/data"
BACKUP_DIR="$PROJECT_ROOT/backups"

# Logging
LOG_FILE="$PROJECT_ROOT/logs/restore.log"
mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

error() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $*" >&2 | tee -a "$LOG_FILE"
    exit 1
}

# Function to show usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS] BACKUP_FILE

Restore Talk2Me UI data from a backup archive.

OPTIONS:
    -d, --dry-run          Show what would be restored without actually doing it
    -f, --force            Force restore even if data directory is not empty
    -l, --list             List available backup files
    -h, --help             Show this help message

BACKUP_FILE:
    Path to the backup archive (.tar.gz file)
    Can be absolute path or relative to project root
    If not specified, will show available backups

EXAMPLES:
    $0 --list                                    # List available backups
    $0 backups/talk2me_backup_20231201_120000.tar.gz  # Restore specific backup
    $0 --dry-run latest                          # Dry run with latest backup
    $0 --force latest                            # Force restore latest backup

ENVIRONMENT VARIABLES:
    RESTORE_VOICES=0|1        Restore voice profiles (default: 1)
    RESTORE_SFX=0|1           Restore sound effects (default: 1)
    RESTORE_BACKGROUND=0|1    Restore background audio (default: 1)
    RESTORE_PROJECTS=0|1      Restore projects (default: 1)
    RESTORE_EXPORTS=0|1       Restore exports (default: 0)
EOF
}

# Parse command line arguments
DRY_RUN=false
FORCE=false
LIST_BACKUPS=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -f|--force)
            FORCE=true
            shift
            ;;
        -l|--list)
            LIST_BACKUPS=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            BACKUP_FILE="$1"
            shift
            ;;
    esac
done

# List available backups if requested
if [[ "$LIST_BACKUPS" == true ]]; then
    log "Available backup files:"
    if [[ -d "$BACKUP_DIR" ]]; then
        find "$BACKUP_DIR" -name "talk2me_backup_*.tar.gz" -type f -printf '%T@ %p\n' | \
            sort -nr | \
            cut -d' ' -f2- | \
            while read -r file; do
                size=$(du -h "$file" | cut -f1)
                date_str=$(basename "$file" | sed 's/talk2me_backup_\([0-9]\{8\}\)_\([0-9]\{6\}\)\.tar\.gz/\1 \2/' | \
                          xargs -I {} date -d "{}" +"%Y-%m-%d %H:%M:%S" 2>/dev/null || echo "Unknown date")
                echo "  $file ($size) - $date_str"
            done
    else
        echo "  No backups directory found"
    fi
    exit 0
fi

# Determine backup file
if [[ -z "${BACKUP_FILE:-}" ]]; then
    error "No backup file specified. Use --list to see available backups."
fi

if [[ "$BACKUP_FILE" == "latest" ]]; then
    if [[ -d "$BACKUP_DIR" ]]; then
        BACKUP_FILE=$(find "$BACKUP_DIR" -name "talk2me_backup_*.tar.gz" -type f -printf '%T@ %p\n' | \
                     sort -nr | head -n1 | cut -d' ' -f2-)
        if [[ -z "$BACKUP_FILE" ]]; then
            error "No backup files found in $BACKUP_DIR"
        fi
    else
        error "Backups directory $BACKUP_DIR does not exist"
    fi
fi

# Convert relative path to absolute
if [[ "$BACKUP_FILE" != /* ]]; then
    BACKUP_FILE="$PROJECT_ROOT/$BACKUP_FILE"
fi

# Check if backup file exists
if [[ ! -f "$BACKUP_FILE" ]]; then
    error "Backup file does not exist: $BACKUP_FILE"
fi

log "Starting restore from backup: $BACKUP_FILE"
if [[ "$DRY_RUN" == true ]]; then
    log "DRY RUN MODE - No actual changes will be made"
fi

# Create temporary directory for extraction
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

# Extract backup to temp directory
log "Extracting backup archive..."
tar -xzf "$BACKUP_FILE" -C "$TEMP_DIR"

# Check backup manifest
if [[ -f "$TEMP_DIR/backup_manifest.txt" ]]; then
    log "Backup manifest:"
    cat "$TEMP_DIR/backup_manifest.txt" | while read -r line; do
        log "  $line"
    done
fi

# Check if data directory has content and warn if not forced
DATA_HAS_CONTENT=false
for dir in voices sfx background projects exports; do
    if [[ -d "$DATA_DIR/$dir" ]] && [[ -n "$(find "$DATA_DIR/$dir" -type f 2>/dev/null)" ]]; then
        DATA_HAS_CONTENT=true
        break
    fi
done

if [[ "$DATA_HAS_CONTENT" == true && "$FORCE" == false ]]; then
    error "Data directory is not empty. Use --force to overwrite existing data."
fi

# Restore function
restore_directory() {
    local src_dir="$1"
    local dst_dir="$2"
    local name="$3"

    if [[ ! -d "$src_dir" ]]; then
        log "Skipping $name - not found in backup"
        return
    fi

    if [[ "$DRY_RUN" == true ]]; then
        log "DRY RUN: Would restore $name from $src_dir to $dst_dir"
        find "$src_dir" -type f | while read -r file; do
            log "  Would restore: $file"
        done
        return
    fi

    log "Restoring $name..."
    mkdir -p "$dst_dir"
    cp -r "$src_dir"/* "$dst_dir"/ 2>/dev/null || true
    log "$name restored successfully"
}

# Restore data based on environment variables
RESTORE_VOICES=${RESTORE_VOICES:-1}
RESTORE_SFX=${RESTORE_SFX:-1}
RESTORE_BACKGROUND=${RESTORE_BACKGROUND:-1}
RESTORE_PROJECTS=${RESTORE_PROJECTS:-1}
RESTORE_EXPORTS=${RESTORE_EXPORTS:-0}

if [[ "$RESTORE_VOICES" == "1" ]]; then
    restore_directory "$TEMP_DIR/voices" "$DATA_DIR/voices" "voice profiles"
fi

if [[ "$RESTORE_SFX" == "1" ]]; then
    restore_directory "$TEMP_DIR/sfx" "$DATA_DIR/sfx" "sound effects"
fi

if [[ "$RESTORE_BACKGROUND" == "1" ]]; then
    restore_directory "$TEMP_DIR/background" "$DATA_DIR/background" "background audio"
fi

if [[ "$RESTORE_PROJECTS" == "1" ]]; then
    restore_directory "$TEMP_DIR/projects" "$DATA_DIR/projects" "projects"
fi

if [[ "$RESTORE_EXPORTS" == "1" ]]; then
    restore_directory "$TEMP_DIR/exports" "$DATA_DIR/exports" "exports"
fi

if [[ "$DRY_RUN" == true ]]; then
    log "DRY RUN completed - no changes made"
else
    log "Restore completed successfully"
    log "Restored from: $BACKUP_FILE"
    log "Data directory: $DATA_DIR"
fi

# Print summary
echo "========================================"
echo "Talk2Me UI Restore Summary"
echo "========================================"
echo "Backup File: $BACKUP_FILE"
echo "Restored: $(date)"
if [[ "$DRY_RUN" == true ]]; then
    echo "Mode: DRY RUN (no changes made)"
else
    echo "Mode: LIVE RESTORE"
fi
echo "Components restored:"
[[ "$RESTORE_VOICES" == "1" ]] && echo "  - Voice profiles"
[[ "$RESTORE_SFX" == "1" ]] && echo "  - Sound effects"
[[ "$RESTORE_BACKGROUND" == "1" ]] && echo "  - Background audio"
[[ "$RESTORE_PROJECTS" == "1" ]] && echo "  - Projects"
[[ "$RESTORE_EXPORTS" == "1" ]] && echo "  - Exports"
echo "========================================"
