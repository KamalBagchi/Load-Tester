#!/bin/bash

# Quick Test Script - Run tests with the latest uploaded endpoints file
echo "🚀 Quick K6 Load Test Runner"

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Change to project root directory
cd "$PROJECT_ROOT"

# Check if any endpoint files exist
if [ ! -d "data/uploads" ] || [ -z "$(ls -A data/uploads/*.json 2>/dev/null)" ]; then
    echo "❌ No endpoint files found in data/uploads/"
    echo "📋 Upload an endpoints.json file through the web interface first"
    echo "   Or copy your endpoints.json file to data/uploads/"
    exit 1
fi

# Get the latest uploaded endpoints file
LATEST_FILE=$(ls -t data/uploads/*.json | head -1)

echo "📁 Using latest endpoints file: $(basename $LATEST_FILE)"
echo "⏰ File uploaded: $(stat -c %y "$LATEST_FILE" 2>/dev/null || stat -f %Sm "$LATEST_FILE" 2>/dev/null)"
echo ""

# Run the test
exec ./scripts/run_tests.sh "$LATEST_FILE"
