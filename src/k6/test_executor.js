// Working example of the flexible routes system for K6 load testing
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
const CONFIG = JSON.parse(open('./endpoints.json'));

// Load configuration once at module level to initialize global state
loadConfiguration(CONFIG);

// K6 test configuration
export let options = {
  stages: [
        { duration: '20s', target: 100 }, 
        { duration: '20s', target: 200 },
        { duration: '20s', target: 300 },
        { duration: '20s', target: 400 },
        { duration: '20s', target: 500 },
        // { duration: '20s', target: 1000 },
        // { duration: '20s', target: 1500 },
        // { duration: '20s', target: 2000 },
        // { duration: '20s', target: 2500 },
        // { duration: '20s', target: 3000 },
        { duration: '1m', target: 500 },
          ],
  thresholds: generateK6Thresholds(),  // Use dynamic thresholds from route configurations
};

// Setup function
export function setup() {
  console.log('=== REX API Load Test Setup ===');
  
  // Validate configuration (already loaded at module level)
  if (!validateConfiguration()) {
    throw new Error('Configuration validation failed');
  }
  
  const routes = getRoutes();
  const scenarios = getScenarios();
  const tokens = getTokens();
  const config = getConfig();
  
  console.log(`✅ Configuration loaded: ${Object.keys(routes).length} routes, ${Object.keys(scenarios).length} scenarios`);
  
  // Log complete configuration details
  console.log('\n=== COMPLETE CONFIGURATION DETAILS ===');
  console.log('Base URL:', getBaseUrl());
  
  console.log('\nTokens:');
  Object.entries(tokens).forEach(([name, token]) => {
    console.log(`  • ${name}: ${token.substring(0, 20)}...`);
  });
  
  console.log('\nK6 Test Options:');
  console.log('  Stages:', JSON.stringify(options.stages, null, 2));
  console.log('  Thresholds:', JSON.stringify(options.thresholds, null, 2));
  
  console.log('\nDetailed Route Configuration:');
  Object.entries(routes).forEach(([name, route]) => {
    const scenario = scenarios[name];
    console.log(`\n  Route: ${name}`);
    console.log(`    Method: ${route.method}`);
    console.log(`    URL: ${route.url}`);
    console.log(`    Description: ${route.description}`);
    console.log(`    Headers:`, JSON.stringify(route.headers, null, 4));
    if (route.payload) {
      console.log(`    Payload:`, JSON.stringify(route.payload, null, 4));
    }
    console.log(`    Weight: ${scenario.weight}%`);
    console.log(`    Think Time: ${scenario.thinkTime.min}-${scenario.thinkTime.max}s`);
    console.log(`    Threshold: ${scenario.threshold_ms}ms`);
  });
  
  console.log('\nScenario Weight Distribution:');
  const totalWeight = Object.values(scenarios).reduce((sum, scenario) => sum + scenario.weight, 0);
  Object.entries(scenarios).forEach(([name, scenario]) => {
    const percentage = ((scenario.weight / totalWeight) * 100).toFixed(1);
    console.log(`  • ${name}: ${scenario.weight} (${percentage}% of traffic)`);
  });
  console.log(`  Total Weight: ${totalWeight}`);
  
  console.log('\nGenerated K6 Thresholds:');
  Object.entries(options.thresholds).forEach(([key, value]) => {
    console.log(`  • ${key}: ${JSON.stringify(value)}`);
  });
  
  console.log('\nOriginal Configuration Object:');
  console.log(JSON.stringify(config, null, 2));
  
  console.log('\n=== Starting Load Test ===\n');
  return CONFIG;
}

// Main test function
export default function(data) {
  // Configuration is already loaded at module level, no need to reload
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
    const hasTimedOut = response.status === 0 && response.error; // k6 sets status 0 for network errors
    
    // Validate response with dynamic threshold - now including timeout checks
    const result = check(response, {
      'status is 2xx': (r) => r.status >= 200 && r.status < 300,
      'no timeout errors': (r) => !isTimeout && !hasTimedOut,
      'no network errors': (r) => r.status !== 0,
      [`response time < ${threshold}ms`]: (r) => r.timings.duration < threshold,
      'response time < 5000ms': (r) => r.timings.duration < 5000,
      'has response body': (r) => r.body && r.body.length > 0,
    }, { route: scenarioName });
    
    // Log detailed info for errors and timeouts
    if (response.status >= 400) {
      console.error(`${scenarioName} failed: ${response.status} ${response.status_text}`);
    }
    if (isTimeout || hasTimedOut) {
      console.error(`${scenarioName} TIMEOUT: ${response.error || 'Request timed out'}`);
    }
  } else {
    // If makeRequest returned null, count this as an error too
    check(null, {
      'request was made': () => false,
    }, { route: scenarioName });
    console.error(`${scenarioName} failed: makeRequest returned null`);
  }
  
  // Think time
  const thinkTime = getThinkTime(scenarioName);
  sleep(thinkTime);
}

// Teardown function
export function teardown(data) {
  console.log('\n=== Load Test Completed ===');
  console.log('Check the results above for performance metrics');
}
