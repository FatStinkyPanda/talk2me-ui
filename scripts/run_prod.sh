#!/bin/bash

# Talk2Me UI Production Server Script
# This script starts the production server with optimized settings

set -e

echo "🚀 Starting Talk2Me UI production server..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run ./scripts/setup.sh first."
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Set environment variables for production
export APP_ENV=production
export LOG_LEVEL=INFO

# Check if .env.prod exists and load it
if [ -f ".env.prod" ]; then
    echo "📄 Loading production environment variables..."
    set -a
    source .env.prod
    set +a
fi

# Set default values if not provided
export HOST=${HOST:-0.0.0.0}
export PORT=${PORT:-8000}
export WORKERS=${WORKERS:-4}

# Create logs directory if it doesn't exist
mkdir -p logs

# Start the production server with multiple workers
echo "🏭 Starting uvicorn with $WORKERS workers on $HOST:$PORT"
echo "📊 API docs available at http://$HOST:$PORT/docs"
echo "📝 Logs will be written to logs/uvicorn.log"
echo "Press Ctrl+C to stop the server"
echo ""

# Run pre-flight checks
echo "🔍 Running pre-flight checks..."
python -c "
import sys
sys.path.insert(0, 'src')
try:
    from talk2me_ui.config import load_config
    config = load_config()
    print('✅ Configuration loaded successfully')
except Exception as e:
    print(f'❌ Configuration error: {e}')
    sys.exit(1)
"

# Start server with production settings
uvicorn src.talk2me_ui.main:app \
    --host $HOST \
    --port $PORT \
    --workers $WORKERS \
    --worker-class uvicorn.workers.UvicornWorker \
    --log-level info \
    --access-log \
    --log-file logs/uvicorn.log \
    --proxy-headers \
    --forwarded-allow-ips "*"

echo "🛑 Server stopped"
