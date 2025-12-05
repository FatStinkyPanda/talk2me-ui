#!/bin/bash

# Talk2Me UI Setup Script
# This script sets up the development environment for the Talk2Me UI application

set -e

echo "🚀 Setting up Talk2Me UI development environment..."

# Check if Python 3.10+ is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.10 or higher."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
REQUIRED_VERSION="3.10"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "❌ Python $PYTHON_VERSION is not supported. Please use Python $REQUIRED_VERSION or higher."
    exit 1
fi

echo "✅ Python $PYTHON_VERSION detected"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📚 Installing dependencies..."
pip install -r requirements.txt

# Create necessary directories
echo "📁 Creating data directories..."
mkdir -p data/sfx
mkdir -p data/background
mkdir -p data/projects

# Copy example config if user config doesn't exist
if [ ! -f "config/user.yaml" ]; then
    echo "⚙️  Setting up configuration..."
    cp config/example.yaml config/user.yaml
    echo "📝 Created config/user.yaml from example. Please edit it with your settings."
fi

# Run database migrations or setup if needed
# (Add any database setup commands here)

echo "🎉 Setup complete!"
echo ""
echo "To start the development server, run:"
echo "  source venv/bin/activate"
echo "  ./scripts/run_dev.sh"
echo ""
echo "For production deployment, run:"
echo "  ./scripts/run_prod.sh"
