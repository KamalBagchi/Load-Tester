#!/bin/bash

# Simple Rate Control Test Runner
# Usage: ./run_simple_rate_control.sh [json_file] [rate_type] [target_rate] [duration]

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Parameters
JSON_FILE=${1:-"a.json"}
RATE_TYPE=${2:-"constant"}
TARGET_RATE=${3:-50}
DURATION=${4:-"5m"}
PRE_ALLOCATED_VUS=${5:-20}
MAX_VUS=${6:-200}

echo -e "${BLUE}🚀 Simple Rate Control Test${NC}"
echo -e "${BLUE}============================${NC}"
echo

echo -e "${YELLOW}Settings:${NC}"
echo -e "  📄 JSON File: ${GREEN}${JSON_FILE}${NC}"
echo -e "  🎯 Rate Type: ${GREEN}${RATE_TYPE}${NC}"
echo -e "  ⚡ Target Rate: ${GREEN}${TARGET_RATE} RPS${NC}"
echo -e "  ⏱️  Duration: ${GREEN}${DURATION}${NC}"
echo -e "  👥 VUs: ${GREEN}${PRE_ALLOCATED_VUS} → ${MAX_VUS}${NC}"
echo

# Check if K6 is installed
if ! command -v k6 &> /dev/null; then
    echo -e "${RED}❌ K6 is not installed${NC}"
    exit 1
fi

# Check if JSON file exists
if [ ! -f "$JSON_FILE" ]; then
    echo -e "${RED}❌ JSON file '$JSON_FILE' not found${NC}"
    exit 1
fi

# Copy JSON file to expected location
cp "$JSON_FILE" a.json

# Generate timestamp
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
REPORT_NAME="simple-rate-control-${TIMESTAMP}"

# Create directories
mkdir -p data/results data/reports

echo -e "${YELLOW}🏃 Starting test...${NC}"

# Set environment variables
export RATE_TYPE="$RATE_TYPE"
export TARGET_RATE="$TARGET_RATE"
export DURATION="$DURATION"
export PRE_ALLOCATED_VUS="$PRE_ALLOCATED_VUS"
export MAX_VUS="$MAX_VUS"

# Custom stages for ramping mode
if [ "$RATE_TYPE" = "ramping" ]; then
    export CUSTOM_STAGES='[
        {"duration": "30s", "target": 20},
        {"duration": "2m", "target": 100},
        {"duration": "1m", "target": 0}
    ]'
    export START_RATE=10
fi

# Run K6 test
k6 run \
    --out json=data/results/${REPORT_NAME}_detailed.json \
    --summary-export data/results/${REPORT_NAME}_summary.json \
    src/k6/simple_rate_control_executor.js

K6_EXIT_CODE=$?

echo
echo -e "${YELLOW}📊 Generating report...${NC}"

# Generate HTML report if possible
if [ -f "src/utils/report_generator.py" ]; then
    python3 src/utils/report_generator.py \
        data/results/${REPORT_NAME}_summary.json \
        data/results/${REPORT_NAME}_detailed.json \
        "Simple Rate Control Test"
    
    if [ -f "${REPORT_NAME}.html" ]; then
        mv "${REPORT_NAME}.html" "data/reports/"
        echo -e "${GREEN}✅ Report: data/reports/${REPORT_NAME}.html${NC}"
    fi
fi

echo
echo -e "${BLUE}📋 Results:${NC}"
if [ $K6_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ Test completed successfully${NC}"
elif [ $K6_EXIT_CODE -eq 99 ]; then
    echo -e "${YELLOW}⚠️  Test completed with some thresholds failed${NC}"
else
    echo -e "${RED}❌ Test failed${NC}"
fi

echo
echo -e "${YELLOW}📁 Files generated:${NC}"
echo -e "  📊 data/results/${REPORT_NAME}_detailed.json"
echo -e "  📋 data/results/${REPORT_NAME}_summary.json"
[ -f "data/reports/${REPORT_NAME}.html" ] && echo -e "  📈 data/reports/${REPORT_NAME}.html"

echo
echo -e "${BLUE}💡 What this test did:${NC}"
case $RATE_TYPE in
    "constant")
        echo -e "  • Maintained ${TARGET_RATE} requests/second for ${DURATION}"
        ;;
    "ramping")
        echo -e "  • Ramped from 10 → 20 → 100 → 0 RPS over time"
        ;;
esac
echo -e "  • Auto-scaled VUs from ${PRE_ALLOCATED_VUS} to max ${MAX_VUS} as needed"
echo -e "  • Tested all endpoints from your JSON file based on their weights"

# Cleanup
rm -f a.json

echo
echo -e "${GREEN}🎉 Done!${NC}"
