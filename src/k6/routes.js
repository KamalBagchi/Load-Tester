import http from 'k6/http';

// Global variables to hold loaded configuration
let CONFIG = {};
let BASE_URL = "";
let TOKENS = {};
let ROUTES = {};
let SCENARIOS = {};
let CONFIGURATION_LOADED = false;

/**
 * Load configuration from a JSON object
 * @param {Object} configData - The configuration data from JSON file
 */
export function loadConfiguration(configData) {
  if (!configData) {
    console.error('No configuration data provided');
    throw new Error('Configuration data is required');
  }
  
  CONFIG = configData;
  BASE_URL = CONFIG.base_url;
  
  // Process tokens
  TOKENS = {};
  if (CONFIG.tokens && Array.isArray(CONFIG.tokens)) {
    CONFIG.tokens.forEach(tokenData => {
      TOKENS[tokenData.name] = tokenData.token;
    });
  }
  
  // Process endpoints into routes
  ROUTES = {};
  SCENARIOS = {};
  
  if (CONFIG.endpoints && Array.isArray(CONFIG.endpoints)) {
    CONFIG.endpoints.forEach(endpoint => {
      const routeName = endpoint.name;
      
      // Use endpoint-specific base_url if available, otherwise use global BASE_URL
      const endpointBaseUrl = endpoint.base_url || BASE_URL;
      
      // Create route configuration
      ROUTES[routeName] = {
        method: endpoint.method,
        url: `${endpointBaseUrl}${endpoint.url}`,
        headers: processHeaders(endpoint.headers),
        description: endpoint.description || `${endpoint.name} endpoint`
      };
      
      // Add payload if exists
      if (endpoint.body) {
        ROUTES[routeName].payload = endpoint.body;
      }
      
      // Create scenario configuration
      SCENARIOS[routeName] = {
        weight: endpoint.weight || 1,
        thinkTime: endpoint.thinkTime || { min: 1, max: 3 },
        threshold_ms: endpoint.threshold_ms || 2000
      };
    });
  }
  
  // Only log when configuration is loaded for the first time
  if (!CONFIGURATION_LOADED) {
    CONFIGURATION_LOADED = true;
  }
  return CONFIG;
}

/**
 * Process headers and replace token placeholders
 * @param {Object} headers - Headers object from configuration
 * @returns {Object} Processed headers
 */
function processHeaders(headers) {
  if (!headers) return {};
  
  const processedHeaders = {};
  
  for (const [key, value] of Object.entries(headers)) {
    if (typeof value === 'string' && value.includes('<') && value.includes('>')) {
      // Extract token name from placeholder like "Bearer <TEACHER_TOKEN>"
      const tokenMatch = value.match(/<([^>]+)>/);
      if (tokenMatch) {
        const tokenName = tokenMatch[1];
        if (TOKENS[tokenName]) {
          processedHeaders[key] = value.replace(`<${tokenName}>`, TOKENS[tokenName]);
        } else {
          console.warn(`Token ${tokenName} not found in configuration`);
          processedHeaders[key] = value;
        }
      } else {
        processedHeaders[key] = value;
      }
    } else {
      processedHeaders[key] = value;
    }
  }
  
  return processedHeaders;
}

// Export getters for configuration data
export function getBaseUrl() {
  return BASE_URL;
}

export function getTokens() {
  return TOKENS;
}

export function getRoutes() {
  return ROUTES;
}

export function getScenarios() {
  return SCENARIOS;
}

export function getConfig() {
  return CONFIG;
}

// Helper function to get authorization header for a route
export function getAuthHeader(authType) {
  return TOKENS[authType] || '';
}

// Helper function to get complete headers for a route
export function getHeaders(route) {
  const headers = { ...route.headers };
  return headers;
}

// Helper function to select scenario based on weights
export function selectScenario() {
  const scenarios = getScenarios();
  const scenarioNames = Object.keys(scenarios);
  
  if (scenarioNames.length === 0) {
    console.error('No scenarios available for selection');
    return null;
  }
  
  const random = Math.random() * 100;
  let cumulative = 0;
  
  for (const [scenarioName, config] of Object.entries(scenarios)) {
    cumulative += config.weight;
    if (random < cumulative) {
      return scenarioName;
    }
  }
  
  // If no scenario was selected (shouldn't happen with proper weights)
  console.error('No scenario was selected - check weight distribution');
  return null;
}

// Helper function to get think time for a scenario
export function getThinkTime(scenarioName) {
  const scenarios = getScenarios();
  const scenario = scenarios[scenarioName];
  if (!scenario || !scenario.thinkTime) {
    return 1; // Default think time
  }
  return scenario.thinkTime.min + Math.random() * (scenario.thinkTime.max - scenario.thinkTime.min);
}

// Helper function to get threshold for a scenario
export function getThreshold(scenarioName) {
  const scenarios = getScenarios();
  const scenario = scenarios[scenarioName];
  if (!scenario || !scenario.threshold_ms) {
    return 2000; // Default threshold
  }
  return scenario.threshold_ms;
}

// Helper function to make HTTP request for a specific route
export function makeRequest(routeName, customPayload = null) {
  const routes = getRoutes();
  const route = routes[routeName];
  
  if (!route) {
    console.error(`Route ${routeName} not found`);
    return null;
  }
  
  const requestConfig = {
    headers: route.headers,
    tags: { route: routeName }  // Add tags for per-route metrics
  };
  
  const payload = customPayload || route.payload;
  
  let response;
  
  switch (route.method.toUpperCase()) {
    case 'GET':
      response = http.get(route.url, requestConfig);
      break;
    case 'POST':
      response = http.post(route.url, JSON.stringify(payload), requestConfig);
      break;
    case 'PUT':
      response = http.put(route.url, JSON.stringify(payload), requestConfig);
      break;
    case 'DELETE':
      response = http.del(route.url, null, requestConfig);
      break;
    case 'PATCH':
      response = http.patch(route.url, JSON.stringify(payload), requestConfig);
      break;
    default:
      console.error(`Unsupported HTTP method: ${route.method}`);
      return null;
  }
  
  return response;
}

// Validation function to ensure configuration is properly loaded
export function validateConfiguration() {
  const routes = getRoutes();
  const scenarios = getScenarios();
  const tokens = getTokens();
  
  if (Object.keys(routes).length === 0) {
    console.warn('No routes configured');
    return false;
  }
  
  if (Object.keys(scenarios).length === 0) {
    console.warn('No scenarios configured');
    return false;
  }
  
  // Check if all scenario weights sum to 100
  const totalWeight = Object.values(scenarios).reduce((sum, scenario) => sum + scenario.weight, 0);
  if (Math.abs(totalWeight - 100) > 0.01) {
    console.warn(`Scenario weights sum to ${totalWeight}, expected 100`);
  }
  
  console.log(`Configuration validated: ${Object.keys(routes).length} routes, ${Object.keys(tokens).length} tokens`);
  return true;
}

// Helper function to generate K6 thresholds based on route configurations
export function generateK6Thresholds() {
  const scenarios = getScenarios();
  const thresholds = {
    http_req_failed: ['rate<0.05'], // Error rate must be below 5%
    checks: ['rate>0.95'], // 95% of checks should pass (includes timeout checks)
    'checks{check:no timeout errors}': ['rate>0.98'], // 98% should not have timeouts
    'checks{check:no network errors}': ['rate>0.98'], // 98% should not have network errors
  };
  
  // Find the maximum threshold to set a global threshold
  const maxThreshold = Math.max(...Object.values(scenarios).map(s => s.threshold_ms || 2000));
  thresholds.http_req_duration = [`p(95)<${maxThreshold}`];
  
  // Add per-route thresholds if needed
  Object.entries(scenarios).forEach(([routeName, scenario]) => {
    const threshold = scenario.threshold_ms || 2000;
    // Add route-specific threshold (can be used with tags)
    thresholds[`http_req_duration{route:${routeName}}`] = [`p(95)<${threshold}`];
    // Add route-specific timeout threshold
    thresholds[`checks{route:${routeName},check:no timeout errors}`] = ['rate>0.95'];
  });
  
  return thresholds;
}
