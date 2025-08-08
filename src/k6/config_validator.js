// Configuration validator utility for routes JSON files
import { loadConfigurationFromFile, validateConfiguration } from './routes.js';

/**
 * Validate a configuration file and provide detailed feedback
 * @param {string} configPath - Path to the configuration JSON file
 * @returns {Object} Validation result with success flag and messages
 */
export function validateConfigFile(configPath) {
  const result = {
    success: false,
    errors: [],
    warnings: [],
    info: []
  };

  try {
    // Load the configuration
    const config = loadConfigurationFromFile(configPath);
    
    // Basic structure validation
    if (!config.base_url) {
      result.errors.push('Missing required field: base_url');
    } else if (!isValidUrl(config.base_url)) {
      result.errors.push('Invalid base_url format');
    }

    if (!config.endpoints || !Array.isArray(config.endpoints)) {
      result.errors.push('Missing or invalid endpoints array');
    } else {
      result.info.push(`Found ${config.endpoints.length} endpoints`);
      
      // Validate each endpoint
      config.endpoints.forEach((endpoint, index) => {
        validateEndpoint(endpoint, index, result);
      });
    }

    if (!config.tokens || !Array.isArray(config.tokens)) {
      result.warnings.push('No tokens configured');
    } else {
      result.info.push(`Found ${config.tokens.length} tokens`);
      
      // Validate tokens
      config.tokens.forEach((token, index) => {
        validateToken(token, index, result);
      });
    }

    // Validate scenario weights
    if (config.endpoints && config.endpoints.length > 0) {
      validateScenarioWeights(config.endpoints, result);
    }

    // Check token usage
    if (config.tokens && config.endpoints) {
      validateTokenUsage(config.tokens, config.endpoints, result);
    }

    // Overall validation
    const overallValid = validateConfiguration();
    if (overallValid && result.errors.length === 0) {
      result.success = true;
      result.info.push('Configuration is valid and ready for use');
    }

  } catch (error) {
    result.errors.push(`Failed to load configuration: ${error.message}`);
  }

  return result;
}

/**
 * Validate a single endpoint configuration
 */
function validateEndpoint(endpoint, index, result) {
  const prefix = `Endpoint ${index + 1} (${endpoint.name || 'unnamed'})`;

  // Required fields
  if (!endpoint.name) {
    result.errors.push(`${prefix}: Missing required field 'name'`);
  }

  if (!endpoint.method) {
    result.errors.push(`${prefix}: Missing required field 'method'`);
  } else {
    const validMethods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'];
    if (!validMethods.includes(endpoint.method.toUpperCase())) {
      result.errors.push(`${prefix}: Invalid HTTP method '${endpoint.method}'`);
    }
  }

  if (!endpoint.url) {
    result.errors.push(`${prefix}: Missing required field 'url'`);
  }

  // Optional but recommended fields
  if (!endpoint.weight) {
    result.warnings.push(`${prefix}: No weight specified, defaulting to 1`);
  } else if (typeof endpoint.weight !== 'number' || endpoint.weight <= 0) {
    result.errors.push(`${prefix}: Weight must be a positive number`);
  }

  if (!endpoint.thinkTime) {
    result.warnings.push(`${prefix}: No thinkTime specified, using default`);
  } else {
    if (!endpoint.thinkTime.min || !endpoint.thinkTime.max) {
      result.errors.push(`${prefix}: thinkTime must have 'min' and 'max' properties`);
    } else if (endpoint.thinkTime.min > endpoint.thinkTime.max) {
      result.errors.push(`${prefix}: thinkTime min cannot be greater than max`);
    }
  }

  // Validate headers if present
  if (endpoint.headers) {
    if (typeof endpoint.headers !== 'object') {
      result.errors.push(`${prefix}: Headers must be an object`);
    }
  }

  // Validate body for methods that support it
  const methodsWithBody = ['POST', 'PUT', 'PATCH'];
  if (methodsWithBody.includes(endpoint.method?.toUpperCase()) && !endpoint.body) {
    result.warnings.push(`${prefix}: ${endpoint.method} method typically requires a body`);
  }
}

/**
 * Validate a single token configuration
 */
function validateToken(token, index, result) {
  const prefix = `Token ${index + 1}`;

  if (!token.name) {
    result.errors.push(`${prefix}: Missing required field 'name'`);
  }

  if (!token.token) {
    result.errors.push(`${prefix}: Missing required field 'token'`);
  } else if (token.token.length < 10) {
    result.warnings.push(`${prefix}: Token seems unusually short`);
  }
}

/**
 * Validate that scenario weights sum to approximately 100
 */
function validateScenarioWeights(endpoints, result) {
  const totalWeight = endpoints.reduce((sum, endpoint) => {
    return sum + (endpoint.weight || 1);
  }, 0);

  if (Math.abs(totalWeight - 100) > 5) {
    result.warnings.push(`Scenario weights sum to ${totalWeight}, recommended to sum to 100 for accurate distribution`);
  } else {
    result.info.push(`Scenario weights sum to ${totalWeight} (good)`);
  }
}

/**
 * Validate that token placeholders in headers match available tokens
 */
function validateTokenUsage(tokens, endpoints, result) {
  const tokenNames = new Set(tokens.map(t => t.name));
  const usedTokens = new Set();

  endpoints.forEach(endpoint => {
    if (endpoint.headers) {
      Object.values(endpoint.headers).forEach(value => {
        if (typeof value === 'string') {
          const matches = value.match(/<([^>]+)>/g);
          if (matches) {
            matches.forEach(match => {
              const tokenName = match.slice(1, -1); // Remove < and >
              usedTokens.add(tokenName);
              
              if (!tokenNames.has(tokenName)) {
                result.errors.push(`Token placeholder '${tokenName}' used in ${endpoint.name} but not defined in tokens array`);
              }
            });
          }
        }
      });
    }
  });

  // Check for unused tokens
  tokenNames.forEach(tokenName => {
    if (!usedTokens.has(tokenName)) {
      result.warnings.push(`Token '${tokenName}' is defined but never used`);
    }
  });

  result.info.push(`Found ${usedTokens.size} token placeholders in use`);
}

/**
 * Simple URL validation
 */
function isValidUrl(string) {
  try {
    new URL(string);
    return true;
  } catch (_) {
    return false;
  }
}

/**
 * Print validation results in a readable format
 */
export function printValidationResults(result) {
  console.log('\n=== Configuration Validation Results ===\n');
  
  if (result.success) {
    console.log('✅ Configuration is VALID\n');
  } else {
    console.log('❌ Configuration has ISSUES\n');
  }

  if (result.errors.length > 0) {
    console.log('🚫 ERRORS:');
    result.errors.forEach(error => console.log(`   - ${error}`));
    console.log('');
  }

  if (result.warnings.length > 0) {
    console.log('⚠️  WARNINGS:');
    result.warnings.forEach(warning => console.log(`   - ${warning}`));
    console.log('');
  }

  if (result.info.length > 0) {
    console.log('ℹ️  INFO:');
    result.info.forEach(info => console.log(`   - ${info}`));
    console.log('');
  }

  return result.success;
}

// K6 usage example - can be used in a K6 script to validate configuration
export function runValidation(configPath = './endpoints.json') {
  console.log(`Validating configuration file: ${configPath}`);
  
  const result = validateConfigFile(configPath);
  const isValid = printValidationResults(result);
  
  return isValid;
}
