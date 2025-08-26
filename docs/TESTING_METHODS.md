# K6 Testing Methods Comparison

This project now supports two different load testing approaches with K6:

## 1. Virtual User Control (VU-based) - `test_executor.js`

### How it works:
- Controls the number of **virtual users** (VUs) that make requests
- Each VU follows a scenario: make request → think time → repeat
- Load is determined by VUs × request frequency

### Configuration:
```javascript
export let options = {
  stages: [
    { duration: '20s', target: 100 },  // Ramp up to 100 VUs
    { duration: '20s', target: 200 },  // Ramp up to 200 VUs
    { duration: '1m', target: 500 },   // Stay at 500 VUs
  ],
};
```

### Best for:
- ✅ Simulating real user behavior with think times
- ✅ Testing user session-based scenarios
- ✅ Understanding system behavior under user load
- ✅ Testing user experience and response times

### Characteristics:
- Request rate varies based on response times
- Slower responses = lower request rate
- Think time affects overall load pattern
- More realistic user simulation

## 2. Request Rate Control (RPS-based) - `rate_control_executor.js`

### How it works:
- Controls the **requests per second** (RPS) directly
- K6 automatically scales VUs to maintain target rate
- Load is determined by target RPS regardless of response times

### Configuration:
```javascript
export let options = {
  scenarios: {
    constant_rate: {
      executor: 'constant-arrival-rate',
      rate: 50,           // 50 requests per second
      timeUnit: '1s',
      duration: '5m',
      preAllocatedVUs: 20,
      maxVUs: 200,        // Scale up to 200 VUs if needed
    },
  },
};
```

### Best for:
- ✅ Capacity planning and SLA validation
- ✅ Testing system throughput limits
- ✅ Predictable load patterns
- ✅ API performance testing

### Characteristics:
- Consistent request rate regardless of response times
- Slower responses = more VUs automatically created
- No think time (interferes with rate control)
- More predictable load generation

## Comparison Table

| Aspect | Virtual User Control | Request Rate Control |
|--------|---------------------|---------------------|
| **Controls** | Number of VUs | Requests per second |
| **Request Rate** | Variable (depends on response time) | Fixed/predictable |
| **VU Scaling** | Manual via stages | Automatic based on response times |
| **Think Time** | ✅ Used between requests | ❌ Not used (interferes with rate) |
| **Real User Simulation** | ✅ High fidelity | ⚠️ Less realistic |
| **Capacity Planning** | ⚠️ Less predictable | ✅ Excellent |
| **SLA Testing** | ⚠️ Harder to control | ✅ Perfect |
| **System Stress Testing** | ✅ Good for user scenarios | ✅ Good for throughput limits |

## Usage Examples

### Virtual User Control
```bash
# Run standard VU-based test
./scripts/run_tests.sh

# Or manually with k6
k6 run src/k6/test_executor.js
```

### Request Rate Control
```bash
# Run constant rate test at 50 RPS
./scripts/run_rate_control.sh --type constant --rate 50 --duration 5m

# Run ramping rate test
./scripts/run_rate_control.sh --type ramping --max-vus 500

# Custom rate test
./scripts/run_rate_control.sh --rate 100 --duration 10m --max-vus 300
```

## When to Use Which Method

### Use Virtual User Control when:
- Testing user experience and journey flows
- Simulating realistic user behavior patterns
- Testing session-based applications
- Understanding user impact of performance issues
- Testing with realistic think times between actions

### Use Request Rate Control when:
- Validating API rate limits and SLAs
- Capacity planning for specific throughput requirements
- Testing system behavior at exact request rates
- Measuring maximum system throughput
- Load testing APIs without user simulation needs

## Key Differences in Results

### Virtual User Control Results:
- Request rate fluctuates based on system performance
- Think time affects overall test duration and patterns
- VU count directly correlates with concurrent sessions
- More realistic user load simulation

### Request Rate Control Results:
- Consistent request rate (or attempts to be)
- VU count scales automatically with response times
- `dropped_iterations` metric shows if target rate cannot be maintained
- More predictable load generation for capacity testing

## Report Differences

Both methods generate the same comprehensive HTML reports, but pay attention to:

### VU-based reports:
- Focus on response times and user experience metrics
- VU timeline shows planned user ramp-up
- Request rate varies naturally

### Rate-based reports:
- Focus on throughput and capacity metrics
- VU timeline shows automatic scaling
- Look for dropped iterations as a capacity indicator
- Request rate should be more consistent

## Choosing the Right Method

1. **For User Experience Testing**: Use Virtual User Control
2. **For API Capacity Planning**: Use Request Rate Control
3. **For Mixed Testing**: Run both methods with different configurations
4. **For SLA Validation**: Use Request Rate Control
5. **For Realistic Load Simulation**: Use Virtual User Control

Both methods use the same endpoint configuration and routing system, so you can easily switch between them based on your testing objectives.
