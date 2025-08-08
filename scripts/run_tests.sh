#!/bin/bash

# Run k6 test with multiple output formats
echo "🚀 Starting k6 load test with comprehensive reporting..."

# Check if endpoints file is provided as argument
if [ $# -eq 0 ]; then
    echo "❌ Usage: $0 <endpoints-file.json>"
    echo "📋 Example: $0 data/uploads/20250808_120143_endpoints.json"
    echo ""
    echo "📁 Available endpoint files:"
    ls -1 data/uploads/*.json 2>/dev/null | head -5
    exit 1
fi

ENDPOINTS_FILE="$1"

# Check if the endpoints file exists
if [ ! -f "$ENDPOINTS_FILE" ]; then
    echo "❌ File not found: $ENDPOINTS_FILE"
    exit 1
fi

# Create timestamp for unique filenames
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")

# Extract report title from the provided config file
REPORT_TITLE=$(python3 -c "
import json
import sys
try:
    with open('$ENDPOINTS_FILE', 'r') as f:
        config = json.load(f)
    title = config.get('report_title', 'k6-load-test-report')
    # Sanitize filename similar to Python script
    import re
    safe_name = re.sub(r'[^\w\s-]', '', title)
    safe_name = re.sub(r'[-\s]+', '-', safe_name)
    safe_name = safe_name.strip('-').lower()
    print(safe_name)
except Exception as e:
    print('k6-load-test-report')
")

TEST_NAME="${REPORT_TITLE}_${TIMESTAMP}"

# Ensure results and reports directories exist
mkdir -p data/results
mkdir -p data/reports

# Copy the endpoints file to the K6 script directory for K6 to use
cp "$ENDPOINTS_FILE" "src/k6/endpoints.json"

echo "📊 Running k6 test with: $(basename $ENDPOINTS_FILE)"
k6 run \
  --summary-export="data/results/${TEST_NAME}_summary.json" \
  --out json="data/results/${TEST_NAME}_detailed.json" \
  src/k6/test_executor.js

# Clean up temporary file
rm -f "src/k6/endpoints.json"

echo "📈 Generating HTML report with interactive charts..."
python3 src/utils/report_generator.py "data/results/${TEST_NAME}_detailed.json" -c "$ENDPOINTS_FILE"

echo "✅ Test completed! Generated files:"
echo "   📄 Summary: data/results/${TEST_NAME}_summary.json"
echo "   📊 Detailed JSON: data/results/${TEST_NAME}_detailed.json"
echo "   🌐 Interactive Report: data/reports/${REPORT_TITLE}-*.html (auto-generated with timestamp)"

echo ""
echo "🌐 Open the interactive report in your browser:"
echo "   Latest report in: data/reports/"
ls -t data/reports/${REPORT_TITLE}*.html | head -1 2>/dev/null

# Optional: Auto-open in browser (uncomment if you have a GUI)
# LATEST_REPORT=$(ls -t data/reports/${REPORT_TITLE}*.html | head -1 2>/dev/null)
# [ -n "$LATEST_REPORT" ] && (xdg-open "$LATEST_REPORT" 2>/dev/null || open "$LATEST_REPORT" 2>/dev/null)
