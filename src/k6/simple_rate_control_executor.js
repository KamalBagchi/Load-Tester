// Simplified Rate Control executor for K6 load testing
// Upload JSON → Configure Rate/Stages → Get Report
import { 
  loadConfiguration,
  getRoutes, 
  getScenarios, 
  selectScenario, 
  getThreshold,
  makeRequest,
  validateConfiguration,
  getBaseUrl,
  getTokens,
  getConfig,
  generateK6Thresholds
} from './routes.js';
import { check } from 'k6';

// Load configuration from JSON file - support both relative paths
let CONFIG;
try {
  // Try from test directory first
  CONFIG = JSON.parse(open('./a.json'));
} catch (e) {
  try {
    // Try from project root
    CONFIG = JSON.parse(open('../../a.json'));
  } catch (e2) {
    // Try current directory
    CONFIG = JSON.parse(open('a.json'));
  }
}

// Load configuration once at module level to initialize global state
loadConfiguration(CONFIG);

// Simple rate control configuration
function getRateControlConfig() {
  const rateType = __ENV.RATE_TYPE || 'constant';
  const config = { scenarios: {} };

  if (rateType === 'constant') {
    // Constant rate: steady requests per second
    config.scenarios.constant_rate = {
      executor: 'constant-arrival-rate',
      rate: parseInt(__ENV.TARGET_RATE) || 50,        // RPS
      timeUnit: '1s',
      duration: __ENV.DURATION || '5m',              // Test duration
      preAllocatedVUs: parseInt(__ENV.PRE_ALLOCATED_VUS) || 20,
      maxVUs: parseInt(__ENV.MAX_VUS) || 200,
    };
  } else if (rateType === 'ramping') {
    // Ramping rate: stages with different RPS targets
    let stages;
    if (__ENV.CUSTOM_STAGES) {
      try {
        stages = JSON.parse(__ENV.CUSTOM_STAGES);
      } catch (e) {
        console.warn('Failed to parse CUSTOM_STAGES, using defaults');
        stages = [
          { duration: '30s', target: 20 },
          { duration: '2m', target: 100 },
          { duration: '1m', target: 0 }
        ];
      }
    } else {
      stages = [
        { duration: '30s', target: 20 },   // ramp up to 20 RPS
        { duration: '2m', target: 100 },   // ramp up to 100 RPS  
        { duration: '1m', target: 0 }      // ramp down to 0 RPS
      ];
    }

    config.scenarios.ramping_rate = {
      executor: 'ramping-arrival-rate',
      startRate: parseInt(__ENV.START_RATE) || 10,
      timeUnit: '1s',
      preAllocatedVUs: parseInt(__ENV.PRE_ALLOCATED_VUS) || 10,
      maxVUs: parseInt(__ENV.MAX_VUS) || 500,
      stages: stages,
    };
  }

  return config;
}

// Generate K6 options
const rateConfig = getRateControlConfig();

export let options = {
  ...rateConfig,
  thresholds: {
    ...generateK6Thresholds(),
    // Rate control thresholds
    'iteration_duration': ['p(95)<3000'],                    // 95% complete within 3s
    'iterations': [`rate>${Math.floor((parseInt(__ENV.TARGET_RATE) || 50) * 0.9)}`], // Maintain 90% of target rate
    'dropped_iterations': ['count<50'],                      // Less than 50 dropped requests
    'http_req_failed': ['rate<0.1'],                        // Less than 10% errors
  },
};

// Setup function
export function setup() {
  console.log('=== 🚀 Simple Rate Control Load Test ===');
  
  const rateType = __ENV.RATE_TYPE || 'constant';
  console.log(`Rate Type: ${rateType.toUpperCase()}`);
  
  // Validate configuration
  if (!validateConfiguration()) {
    throw new Error('Configuration validation failed');
  }
  
  const routes = getRoutes();
  const scenarios = getScenarios();
  
  console.log(`✅ Loaded ${Object.keys(routes).length} API endpoints from your JSON file`);
  console.log(`📍 Base URL: ${getBaseUrl()}`);
  
  // Log rate configuration
  console.log('\n=== 📊 RATE CONTROL SETTINGS ===');
  const activeScenario = Object.keys(options.scenarios)[0];
  const scenarioConfig = options.scenarios[activeScenario];
  
  if (scenarioConfig.executor === 'constant-arrival-rate') {
    console.log(`🎯 Target Rate: ${scenarioConfig.rate} requests/second`);
    console.log(`⏱️  Duration: ${scenarioConfig.duration}`);
    console.log(`👥 VUs: ${scenarioConfig.preAllocatedVUs} → ${scenarioConfig.maxVUs} (auto-scaling)`);
    console.log(`📈 Expected Total Requests: ~${calculateTotalRequests(scenarioConfig)}`);
  } else if (scenarioConfig.executor === 'ramping-arrival-rate') {
    console.log(`🎯 Start Rate: ${scenarioConfig.startRate} requests/second`);
    console.log(`👥 VUs: ${scenarioConfig.preAllocatedVUs} → ${scenarioConfig.maxVUs} (auto-scaling)`);
    console.log(`📈 Expected Total Requests: ~${calculateRampingRequests(scenarioConfig)}`);
    
    console.log('\n📊 Ramping Stages:');
    scenarioConfig.stages.forEach((stage, index) => {
      console.log(`   ${index + 1}. ${stage.duration} → ${stage.target} RPS`);
    });
  }
  
  // Show endpoint distribution
  console.log('\n=== 🎲 ENDPOINT DISTRIBUTION ===');
  const totalWeight = Object.values(scenarios).reduce((sum, scenario) => sum + scenario.weight, 0);
  Object.entries(scenarios).forEach(([name, scenario]) => {
    const percentage = ((scenario.weight / totalWeight) * 100).toFixed(1);
    console.log(`   • ${name}: ${percentage}% of requests`);
  });
  
  console.log('\n=== ✨ RATE CONTROL BENEFITS ===');
  console.log('   ✓ Predictable load - maintains steady RPS regardless of response times');
  console.log('   ✓ Auto-scaling VUs - adds more users if responses are slow');
  console.log('   ✓ Real-world simulation - mimics actual traffic patterns');
  console.log('   ✓ Better capacity planning - clear RPS targets for your system');
  
  console.log('\n🚀 Starting rate control test...\n');
  return CONFIG;
}

// Main test function - one request per iteration
export default function(data) {
  // Select which API endpoint to test (based on weights in your JSON)
  const scenarioName = selectScenario();
  
  if (!scenarioName) {
    console.warn('❌ No endpoint selected');
    return;
  }
  
  // Make the API request
  const response = makeRequest(scenarioName);
  
  if (response) {
    // Get expected response time for this endpoint
    const threshold = getThreshold(scenarioName);
    
    // Validate the response
    const result = check(response, {
      '✅ Status 2xx': (r) => r.status >= 200 && r.status < 300,
      '⚡ No timeouts': (r) => !isTimeoutError(r),
      '🌐 No network errors': (r) => r.status !== 0,
      '📄 Has response body': (r) => r.body && r.body.length > 0,
      [`⏱️  Response < ${threshold}ms`]: (r) => r.timings.duration < threshold,
      '🚀 Quick response': (r) => r.timings.duration < 2000, // For rate sustainability
    }, { 
      endpoint: scenarioName,
      test_type: 'rate_control'
    });
    
    // Log issues
    if (response.status >= 400) {
      console.error(`❌ ${scenarioName} failed: ${response.status} ${response.status_text}`);
    }
    if (isTimeoutError(response)) {
      console.error(`⏰ ${scenarioName} TIMEOUT: ${response.error || 'Request timed out'}`);
    }
    if (response.timings.duration > 3000) {
      console.warn(`🐌 ${scenarioName} slow response: ${response.timings.duration.toFixed(0)}ms (may affect rate control)`);
    }
    
  } else {
    check(null, { '❌ Request failed': () => false }, { endpoint: scenarioName });
    console.error(`❌ ${scenarioName} failed to execute`);
  }
  
  // Note: No sleep() in rate control - K6 handles timing automatically
}

// Helper functions
function isTimeoutError(response) {
  return (response.error && response.error.includes('request timeout')) || 
         (response.status === 0 && response.error);
}

function calculateTotalRequests(config) {
  const duration = parseDuration(config.duration);
  const rate = config.rate;
  return Math.round(duration * rate);
}

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

// Teardown function
export function teardown(data) {
  console.log('\n=== ✅ Rate Control Test Completed ===');
  console.log('📊 Check your results:');
  console.log('   • Iteration rate vs target rate');
  console.log('   • Response times per endpoint'); 
  console.log('   • Error rates');
  console.log('   • VU utilization');
  
  console.log('\n💡 Rate Control Analysis:');
  console.log('   • If dropped iterations > 0: Your system hit capacity limits');
  console.log('   • If VUs scaled up: Responses were slower than expected');
  console.log('   • If error rate increased: System may be overloaded');
  console.log('   • Consistent rate = Good system capacity for this load');
}
