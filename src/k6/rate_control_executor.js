// Request Rate Control executor for K6 load testing
// Controls requests per second (RPS) instead of virtual users
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
} from './routes.js';
import { check, sleep } from 'k6';

// Load configuration from JSON file
const CONFIG = JSON.parse(open('../../a.json'));

// Load configuration once at module level to initialize global state
loadConfiguration(CONFIG);

// K6 test configuration with rate-based execution
export let options = {
  scenarios: {
    // Constant Request Rate scenario
    constant_rate: {
      executor: 'constant-arrival-rate',
      rate: 50,           // 50 requests per second
      timeUnit: '1s',     // per second
      duration: '5m',     // for 5 minutes
      preAllocatedVUs: 20, // initial VUs
      maxVUs: 200,        // maximum VUs if needed
    },
    
    // Ramping Request Rate scenario (commented out - use one at a time)
    /*
    ramping_rate: {
      executor: 'ramping-arrival-rate',
      startRate: 10,      // start with 10 RPS
      timeUnit: '1s',
      preAllocatedVUs: 10,
      maxVUs: 500,
      stages: [
        { duration: '30s', target: 20 },   // ramp up to 20 RPS
        { duration: '1m', target: 50 },    // ramp up to 50 RPS
        { duration: '2m', target: 100 },   // ramp up to 100 RPS
        { duration: '1m', target: 200 },   // ramp up to 200 RPS
        { duration: '2m', target: 200 },   // stay at 200 RPS
        { duration: '1m', target: 100 },   // ramp down to 100 RPS
        { duration: '30s', target: 50 },   // ramp down to 50 RPS
        { duration: '30s', target: 0 },    // ramp down to 0 RPS
      ],
    },
    */
  },
  thresholds: {
    ...generateK6Thresholds(),  // Use dynamic thresholds from route configurations
    // Additional rate-specific thresholds
    'iteration_duration': ['p(95)<2000'], // 95% of iterations should complete within 2s
    'iterations': ['rate>45'],            // Should maintain at least 45 iterations/sec
    'dropped_iterations': ['count<100'],   // Less than 100 dropped iterations
  },
};

// Setup function
export function setup() {
  console.log('=== REX API Rate Control Load Test Setup ===');
  
  // Validate configuration (already loaded at module level)
  if (!validateConfiguration()) {
    throw new Error('Configuration validation failed');
  }
  
  const routes = getRoutes();
  const scenarios = getScenarios();
  const tokens = getTokens();
  const config = getConfig();
  
  console.log(`✅ Configuration loaded: ${Object.keys(routes).length} routes, ${Object.keys(scenarios).length} scenarios`);
  
  // Log rate control specific configuration
  console.log('\n=== RATE CONTROL CONFIGURATION ===');
  console.log('Execution Type: Request Rate Control');
  console.log('Base URL:', getBaseUrl());
  
  // Log the active scenario configuration
  const activeScenario = Object.keys(options.scenarios)[0];
  const scenarioConfig = options.scenarios[activeScenario];
  
  console.log(`\nActive Scenario: ${activeScenario}`);
  console.log(`  Executor: ${scenarioConfig.executor}`);
  
  if (scenarioConfig.executor === 'constant-arrival-rate') {
    console.log(`  Request Rate: ${scenarioConfig.rate} requests/${scenarioConfig.timeUnit}`);
    console.log(`  Duration: ${scenarioConfig.duration}`);
    console.log(`  Pre-allocated VUs: ${scenarioConfig.preAllocatedVUs}`);
    console.log(`  Max VUs: ${scenarioConfig.maxVUs}`);
    console.log(`  Expected Total Requests: ~${calculateTotalRequests(scenarioConfig)}`);
  } else if (scenarioConfig.executor === 'ramping-arrival-rate') {
    console.log(`  Start Rate: ${scenarioConfig.startRate} requests/${scenarioConfig.timeUnit}`);
    console.log(`  Pre-allocated VUs: ${scenarioConfig.preAllocatedVUs}`);
    console.log(`  Max VUs: ${scenarioConfig.maxVUs}`);
    console.log(`  Stages:`, JSON.stringify(scenarioConfig.stages, null, 4));
    console.log(`  Expected Total Requests: ~${calculateRampingRequests(scenarioConfig)}`);
  }
  
  console.log('\nTokens:');
  Object.entries(tokens).forEach(([name, token]) => {
    console.log(`  • ${name}: ${token.substring(0, 20)}...`);
  });
  
  console.log('\nRate Control Thresholds:');
  Object.entries(options.thresholds).forEach(([key, value]) => {
    console.log(`  • ${key}: ${JSON.stringify(value)}`);
  });
  
  console.log('\nDetailed Route Configuration:');
  Object.entries(routes).forEach(([name, route]) => {
    const scenario = scenarios[name];
    console.log(`\n  Route: ${name}`);
    console.log(`    Method: ${route.method}`);
    console.log(`    URL: ${route.url}`);
    console.log(`    Description: ${route.description}`);
    console.log(`    Weight: ${scenario.weight}%`);
    console.log(`    Think Time: ${scenario.thinkTime.min}-${scenario.thinkTime.max}s`);
    console.log(`    Threshold: ${scenario.threshold_ms}ms`);
  });
  
  console.log('\nScenario Weight Distribution:');
  const totalWeight = Object.values(scenarios).reduce((sum, scenario) => sum + scenario.weight, 0);
  Object.entries(scenarios).forEach(([name, scenario]) => {
    const percentage = ((scenario.weight / totalWeight) * 100).toFixed(1);
    console.log(`  • ${name}: ${scenario.weight} (${percentage}% of requests)`);
  });
  console.log(`  Total Weight: ${totalWeight}`);
  
  console.log('\n=== Rate Control Benefits ===');
  console.log('✓ Predictable request rate regardless of response times');
  console.log('✓ Better simulation of real-world traffic patterns');
  console.log('✓ Easier capacity planning and SLA validation');
  console.log('✓ Automatic VU scaling based on response times');
  console.log('✓ More realistic load distribution');
  
  console.log('\n=== Starting Rate Control Load Test ===\n');
  return CONFIG;
}

// Helper function to calculate total requests for constant rate
function calculateTotalRequests(config) {
  const duration = parseDuration(config.duration);
  const rate = config.rate;
  return Math.round(duration * rate);
}

// Helper function to calculate total requests for ramping rate
function calculateRampingRequests(config) {
  let total = 0;
  let currentRate = config.startRate;
  
  for (const stage of config.stages) {
    const duration = parseDuration(stage.duration);
    const targetRate = stage.target;
    const avgRate = (currentRate + targetRate) / 2;
    total += Math.round(duration * avgRate);
    currentRate = targetRate;
  }
  
  return total;
}

// Helper function to parse duration strings
function parseDuration(duration) {
  const match = duration.match(/^(\d+)([smh])$/);
  if (!match) return 0;
  
  const value = parseInt(match[1]);
  const unit = match[2];
  
  switch (unit) {
    case 's': return value;
    case 'm': return value * 60;
    case 'h': return value * 3600;
    default: return 0;
  }
}

// Main test function - simplified for rate control
export default function(data) {
  // Configuration is already loaded at module level
  
  // Select scenario based on weights
  const scenarioName = selectScenario();
  
  if (!scenarioName) {
    console.warn('No scenario selected');
    return;
  }
  
  // Make the API request
  const response = makeRequest(scenarioName);
  
  if (response) {
    // Get the threshold for this specific scenario
    const threshold = getThreshold(scenarioName);
    
    // Check if this is a timeout error
    const isTimeout = response.error && response.error.includes('request timeout');
    const hasTimedOut = response.status === 0 && response.error;
    
    // Validate response with dynamic threshold
    const result = check(response, {
      'status is 2xx': (r) => r.status >= 200 && r.status < 300,
      'no timeout errors': (r) => !isTimeout && !hasTimedOut,
      'no network errors': (r) => r.status !== 0,
      [`response time < ${threshold}ms`]: (r) => r.timings.duration < threshold,
      'response time < 5000ms': (r) => r.timings.duration < 5000,
      'has response body': (r) => r.body && r.body.length > 0,
      // Rate control specific checks
      'quick response': (r) => r.timings.duration < 1000, // For rate sustainability
    }, { 
      route: scenarioName,
      execution_type: 'rate_control'
    });
    
    // Log detailed info for errors and timeouts
    if (response.status >= 400) {
      console.error(`${scenarioName} failed: ${response.status} ${response.status_text}`);
    }
    if (isTimeout || hasTimedOut) {
      console.error(`${scenarioName} TIMEOUT: ${response.error || 'Request timed out'}`);
    }
    
    // Log slow responses that might affect rate sustainability
    if (response.timings.duration > 2000) {
      console.warn(`${scenarioName} slow response: ${response.timings.duration.toFixed(0)}ms (may affect rate control)`);
    }
    
  } else {
    // If makeRequest returned null, count this as an error
    check(null, {
      'request was made': () => false,
    }, { 
      route: scenarioName,
      execution_type: 'rate_control'
    });
    console.error(`${scenarioName} failed: makeRequest returned null`);
  }
  
  // Note: In rate control mode, we don't use sleep/think time
  // K6 handles the timing automatically to maintain the target rate
  // Think time would interfere with rate control accuracy
}

// Teardown function
export function teardown(data) {
  console.log('\n=== Rate Control Load Test Completed ===');
  console.log('📊 Rate Control Test Results Summary:');
  console.log('   • Check iteration rate vs target rate');
  console.log('   • Review dropped iterations (should be minimal)');
  console.log('   • Analyze VU utilization patterns');
  console.log('   • Verify response time consistency under rate pressure');
  console.log('\n💡 Rate Control Insights:');
  console.log('   • High response times = More VUs needed to maintain rate');
  console.log('   • Dropped iterations = Server cannot handle target rate');
  console.log('   • Consistent rate = Good server capacity for target load');
}
