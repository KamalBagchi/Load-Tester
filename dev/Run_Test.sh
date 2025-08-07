#!/bin/bash

# Run k6 test with multiple output formats
echo "🚀 Starting k6 load test with comprehensive reporting..."

# Create timestamp for unique filenames
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")

# Extract report title from config and create consistent naming
REPORT_TITLE=$(python3 -c "
import json
try:
    with open('endpoints.json', 'r') as f:
        config = json.load(f)
    title = config.get('report_title', 'k6-load-test-report')
    # Sanitize filename similar to Python script
    import re
    safe_name = re.sub(r'[^\w\s-]', '', title)
    safe_name = re.sub(r'[-\s]+', '-', safe_name)
    safe_name = safe_name.strip('-').lower()
    print(safe_name)
except:
    print('k6-load-test-report')
")

TEST_NAME="${REPORT_TITLE}_${TIMESTAMP}"

# Ensure results and reports directories exist
mkdir -p results
mkdir -p reports

echo "📊 Running k6 test..."
k6 run \
  --summary-export="results/${TEST_NAME}_summary.json" \
  --out json="results/${TEST_NAME}_detailed.json" \
  Load_Test_Executor.js

echo "📈 Generating HTML report with interactive charts..."
python3 Generate_Report.py "results/${TEST_NAME}_detailed.json"

echo "✅ Test completed! Generated files:"
echo "   📄 Summary: results/${TEST_NAME}_summary.json"
echo "   📊 Detailed JSON: results/${TEST_NAME}_detailed.json"
echo "   📈 CSV Metrics: results/${TEST_NAME}_metrics.csv"
echo "   🌐 Interactive Report: reports/${REPORT_TITLE}-*.html (auto-generated with timestamp)"

echo ""
echo "🌐 Open the interactive report in your browser:"
echo "   Latest report in: reports/${REPORT_TITLE}-*.html"

# Optional: Auto-open in browser (uncomment if you have a GUI)
# Latest report: xdg-open "reports/${REPORT_TITLE}"-*.html 2>/dev/null || open "reports/${REPORT_TITLE}"-*.html 2>/dev/null
