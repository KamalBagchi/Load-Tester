#!/bin/bash

# K6 Load Testing Web Interface Startup Script
echo "🚀 Starting K6 Load Testing Web Interface..."

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Change to project root directory
cd "$PROJECT_ROOT"

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    echo "📋 Install Python 3 from: https://www.python.org/downloads/"
    exit 1
fi

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 is required but not installed."
    echo "📋 Install pip3 with: python3 -m ensurepip --upgrade"
    exit 1
fi

# Check if K6 is installed
if ! command -v k6 &> /dev/null; then
    echo "❌ K6 is required but not installed."
    echo "📋 Install K6 from: https://k6.io/docs/get-started/installation/"
    echo ""
    echo "   # Linux/macOS:"
    echo "   curl -s https://get.k6.io | bash"
    echo ""
    echo "   # Windows (with Chocolatey):"
    echo "   choco install k6"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "📦 Creating Python virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Install/upgrade dependencies
echo "📚 Installing/upgrading dependencies..."
pip install -r requirements.txt

# Create necessary directories with proper structure
echo "📁 Creating directory structure..."
mkdir -p data/uploads data/results data/reports
mkdir -p src/web/static/css src/web/static/js
mkdir -p src/web/routes

# Set proper permissions
chmod +x scripts/*.sh
chmod +x src/web/app.py

# Verify directory structure
echo "✅ Directory structure verified:"
echo "   📤 data/uploads/     - For uploaded endpoint configurations"
echo "   📊 data/results/     - For K6 test results"
echo "   📋 data/reports/     - For generated HTML reports"

echo ""
echo "✅ Setup complete!"
echo ""
echo "🌐 Starting web server..."
echo "📍 The web interface will be available at: http://localhost:5000"
echo "🛑 Press Ctrl+C to stop the server"
echo ""

# Change to the web directory and start the Flask application
cd src/web
python3 app.py
