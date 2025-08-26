#!/bin/bash

# K6 Rate Control Test Runner
# Provides easy execution of rate-controlled load tests

set -e

# Default values
CONFIG_FILE="a copy.json"
OUTPUT_DIR="data/results"
REPORTS_DIR="data/reports"
RATE_TYPE="constant"
RATE_VALUE="10"
DURATION="1m"
MAX_VUS="20"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}$1${NC}"
}

# Help function
show_help() {
    cat << EOF
K6 Rate Control Test Runner

USAGE:
    $0 [OPTIONS]

OPTIONS:
    -t, --type TYPE        Rate control type: 'constant' or 'ramping' (default: constant)
    -r, --rate RATE        Requests per second for constant rate (default: 50)
    -d, --duration TIME    Test duration (default: 5m)
    -m, --max-vus VUS      Maximum virtual users (default: 200)
    -c, --config FILE      Configuration file (default: endpoints.json)
    -o, --output DIR       Output directory (default: data/results)
    --reports DIR          Reports directory (default: data/reports)
    -h, --help             Show this help message

EXAMPLES:
    # Run constant rate test at 50 RPS for 5 minutes
    $0

    # Run constant rate test at 100 RPS for 10 minutes
    $0 --type constant --rate 100 --duration 10m

    # Run ramping rate test
    $0 --type ramping --max-vus 500

    # Custom configuration and output
    $0 --config custom.json --output /tmp/results

RATE TYPES:
    constant    - Maintains steady requests per second
    ramping     - Gradually increases/decreases request rate
EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--type)
            RATE_TYPE="$2"
            shift 2
            ;;
        -r|--rate)
            RATE_VALUE="$2"
            shift 2
            ;;
        -d|--duration)
            DURATION="$2"
            shift 2
            ;;
        -m|--max-vus)
            MAX_VUS="$2"
            shift 2
            ;;
        -c|--config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        -o|--output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --reports)
            REPORTS_DIR="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Validate rate type
if [[ "$RATE_TYPE" != "constant" && "$RATE_TYPE" != "ramping" ]]; then
    print_error "Invalid rate type: $RATE_TYPE. Must be 'constant' or 'ramping'"
    exit 1
fi

# Check if k6 is installed
if ! command -v k6 &> /dev/null; then
    print_error "k6 is not installed. Please install k6 first."
    print_status "Visit: https://k6.io/docs/getting-started/installation/"
    exit 1
fi

# Check if configuration file exists
if [[ ! -f "$CONFIG_FILE" ]]; then
    print_error "Configuration file not found: $CONFIG_FILE"
    exit 1
fi

# Create output directories
mkdir -p "$OUTPUT_DIR"
mkdir -p "$REPORTS_DIR"

# Generate timestamp for unique filenames
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
TEST_NAME="rate-control-${RATE_TYPE}-${TIMESTAMP}"

# Create temporary k6 script with specified parameters
TEMP_SCRIPT="temp_rate_control_${TIMESTAMP}.js"

print_header "=== K6 Rate Control Load Test ==="
print_status "Test Type: ${RATE_TYPE} rate control"
print_status "Configuration: $CONFIG_FILE"
print_status "Output Directory: $OUTPUT_DIR"
print_status "Reports Directory: $REPORTS_DIR"

if [[ "$RATE_TYPE" == "constant" ]]; then
    print_status "Request Rate: ${RATE_VALUE} RPS"
    print_status "Duration: $DURATION"
fi

print_status "Max VUs: $MAX_VUS"
print_status "Test ID: $TEST_NAME"

# Create the temporary script with custom parameters
cat > "$TEMP_SCRIPT" << EOF
// Auto-generated rate control script
import { 
  loadConfiguration,
  getRoutes, 
  getScenarios, 
  selectScenario, 
  getThinkTime,
  getThreshold,
  makeRequest,
  validateConfiguration,
  getBaseUrl,
  getTokens,
  getConfig,
  generateK6Thresholds
} from './src/k6/routes.js';
import { check, sleep } from 'k6';

const CONFIG = JSON.parse(open('$CONFIG_FILE'));
loadConfiguration(CONFIG);

export let options = {
  scenarios: {
EOF

if [[ "$RATE_TYPE" == "constant" ]]; then
    # Ensure preAllocatedVUs is not more than maxVUs
    PRE_ALLOCATED_VUS=$(( MAX_VUS < 20 ? MAX_VUS : 20 ))
    cat >> "$TEMP_SCRIPT" << EOF
    constant_rate: {
      executor: 'constant-arrival-rate',
      rate: $RATE_VALUE,
      timeUnit: '1s',
      duration: '$DURATION',
      preAllocatedVUs: $PRE_ALLOCATED_VUS,
      maxVUs: $MAX_VUS,
    },
EOF
else
    # Ensure preAllocatedVUs is not more than maxVUs for ramping
    PRE_ALLOCATED_VUS=$(( MAX_VUS < 20 ? MAX_VUS : 20 ))
    cat >> "$TEMP_SCRIPT" << EOF
    ramping_rate: {
      executor: 'ramping-arrival-rate',
      startRate: 10,
      timeUnit: '1s',
      preAllocatedVUs: $PRE_ALLOCATED_VUS,
      maxVUs: $MAX_VUS,
      stages: [
        { duration: '30s', target: 20 },
        { duration: '1m', target: 50 },
        { duration: '2m', target: 100 },
        { duration: '1m', target: 200 },
        { duration: '2m', target: 200 },
        { duration: '1m', target: 100 },
        { duration: '30s', target: 50 },
        { duration: '30s', target: 0 },
      ],
    },
EOF
fi

cat >> "$TEMP_SCRIPT" << EOF
  },
  thresholds: {
    ...generateK6Thresholds(),
    'iteration_duration': ['p(95)<2000'],
    'iterations': ['rate>45'],
    'dropped_iterations': ['count<100'],
  },
};

export function setup() {
  console.log('=== Rate Control Load Test Setup ===');
  if (!validateConfiguration()) {
    throw new Error('Configuration validation failed');
  }
  console.log('✅ Configuration loaded successfully');
  console.log('🎯 Rate Type: $RATE_TYPE');
  return CONFIG;
}

export default function(data) {
  const scenarioName = selectScenario();
  if (!scenarioName) return;
  
  const response = makeRequest(scenarioName);
  if (response) {
    const threshold = getThreshold(scenarioName);
    const isTimeout = response.error && response.error.includes('request timeout');
    const hasTimedOut = response.status === 0 && response.error;
    
    check(response, {
      'status is 2xx': (r) => r.status >= 200 && r.status < 300,
      'no timeout errors': (r) => !isTimeout && !hasTimedOut,
      'no network errors': (r) => r.status !== 0,
      [\`response time < \${threshold}ms\`]: (r) => r.timings.duration < threshold,
      'response time < 5000ms': (r) => r.timings.duration < 5000,
      'has response body': (r) => r.body && r.body.length > 0,
      'quick response': (r) => r.timings.duration < 1000,
    }, { 
      route: scenarioName,
      execution_type: 'rate_control'
    });
    
    if (response.status >= 400) {
      console.error(\`\${scenarioName} failed: \${response.status} \${response.status_text}\`);
    }
    if (isTimeout || hasTimedOut) {
      console.error(\`\${scenarioName} TIMEOUT: \${response.error || 'Request timed out'}\`);
    }
  } else {
    check(null, { 'request was made': () => false }, { route: scenarioName });
  }
}

export function teardown(data) {
  console.log('=== Rate Control Test Completed ===');
}
EOF

print_status "Starting rate control test..."

# Run the k6 test
k6 run \
  --out json="${OUTPUT_DIR}/${TEST_NAME}_detailed.json" \
  --summary-export="${OUTPUT_DIR}/${TEST_NAME}_summary.json" \
  "$TEMP_SCRIPT"

# Check if test completed successfully
if [[ $? -eq 0 ]]; then
    print_status "✅ Test completed successfully!"
    
    # Generate HTML report if report generator exists
    if [[ -f "src/utils/report_generator.py" ]]; then
        print_status "📊 Generating HTML report..."
        
        # Use Python to generate the report
        if command -v python3 &> /dev/null; then
            python3 src/utils/report_generator.py \
                "${OUTPUT_DIR}/${TEST_NAME}_detailed.json" \
                -o "${REPORTS_DIR}/${TEST_NAME}-report.html" \
                -c "$CONFIG_FILE" 2>/dev/null || true
        elif command -v python &> /dev/null; then
            python src/utils/report_generator.py \
                "${OUTPUT_DIR}/${TEST_NAME}_detailed.json" \
                -o "${REPORTS_DIR}/${TEST_NAME}-report.html" \
                -c "$CONFIG_FILE" 2>/dev/null || true
        fi
        
        if [[ -f "${REPORTS_DIR}/${TEST_NAME}-report.html" ]]; then
            print_status "📊 HTML report generated: ${REPORTS_DIR}/${TEST_NAME}-report.html"
        fi
    fi
    
    print_header "=== Test Results Summary ==="
    print_status "Test ID: $TEST_NAME"
    print_status "Detailed Results: ${OUTPUT_DIR}/${TEST_NAME}_detailed.json"
    print_status "Summary Results: ${OUTPUT_DIR}/${TEST_NAME}_summary.json"
    
    if [[ -f "${REPORTS_DIR}/${TEST_NAME}-report.html" ]]; then
        print_status "HTML Report: ${REPORTS_DIR}/${TEST_NAME}-report.html"
    fi
    
    print_header "=== Rate Control Analysis Tips ==="
    print_warning "• Check 'iterations' metric for actual request rate achieved"
    print_warning "• Monitor 'dropped_iterations' - should be minimal"
    print_warning "• High VU count indicates slow response times"
    print_warning "• Rate control automatically scales VUs based on response times"
    
else
    print_error "❌ Test failed!"
    exit 1
fi

# Cleanup temporary script
rm -f "$TEMP_SCRIPT"

print_status "🎉 Rate control test execution complete!"
