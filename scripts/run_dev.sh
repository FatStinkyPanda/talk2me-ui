#!/bin/bash

# Talk2Me UI Development Server Script
# This script starts the development server with hot reload

set -e

echo "🚀 Starting Talk2Me UI development server..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run ./scripts/setup.sh first."
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Set environment variables for development
export APP_ENV=development
export LOG_LEVEL=DEBUG

# Check if .env.dev exists and load it
if [ -f ".env.dev" ]; then
    echo "📄 Loading development environment variables..."
    set -a
    source .env.dev
    set +a
fi

# Start the development server with hot reload
echo "🔄 Starting uvicorn with hot reload on http://localhost:8000"
echo "📊 API docs available at http://localhost:8000/docs"
echo "Press Ctrl+C to stop the server"
echo ""

uvicorn src.talk2me_ui.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    --reload-dir src \
    --reload-dir config \
    --log-level debug \
    --access-log
