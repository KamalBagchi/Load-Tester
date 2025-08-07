#!/usr/bin/env python3
"""
k6 Test Results Report Generator with Interactive Charts
Creates a comprehensive HTML report with graphs using Chart.js
"""

import json
import argparse
import os
import re
from datetime import datetime
from collections import defaultdict
import statistics

def sanitize_filename(title):
    """Convert report title to a safe filename"""
    # Remove/replace invalid characters for filenames
    safe_name = re.sub(r'[^\w\s-]', '', title)
    # Replace spaces and multiple dashes with single dash
    safe_name = re.sub(r'[-\s]+', '-', safe_name)
    # Remove leading/trailing dashes and convert to lowercase
    safe_name = safe_name.strip('-').lower()
    return safe_name

def load_routes_config(config_file='endpoints.json'):
    """Load routes configuration to get endpoint names and thresholds"""
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        # Try alternative paths if the default doesn't work
        alt_paths = ['dev/endpoints.json', '../endpoints.json']
        for alt_path in alt_paths:
            try:
                with open(alt_path, 'r') as f:
                    config = json.load(f)
                print(f"✅ Found config file at: {alt_path}")
                return config
            except FileNotFoundError:
                continue
        
        print(f"⚠️ Routes config file {config_file} not found, using defaults")
        return {}

def get_endpoint_info_from_config(url, method, config):
    """Get endpoint name and threshold from config based on URL and method"""
    if not config or 'endpoints' not in config:
        return None, None
    
    for endpoint in config['endpoints']:
        endpoint_url = endpoint.get('url', '')
        endpoint_method = endpoint.get('method', 'GET')
        endpoint_name = endpoint.get('name', '')
        
        # Match by URL pattern and method
        # Check if the endpoint URL (without leading slash) is in the full URL
        clean_endpoint_url = endpoint_url.lstrip('/')
        if clean_endpoint_url in url and endpoint_method.upper() == method.upper():
            return endpoint_name, endpoint.get('description', endpoint_name)
    
    return None, None

def analyze_k6_json_with_timeline(json_file, config_file='endpoints.json'):
    """Analyze k6 JSON output and extract metrics with timeline data"""
    print(f"🔍 Analyzing {json_file} with timeline data...")
    
    # Load routes configuration
    routes_config = load_routes_config(config_file)
    
    response_times = []
    timeline_data = []
    error_count = 0
    total_requests = 0
    endpoint_stats = defaultdict(lambda: {
        'response_times': [],
        'timeline': [],
        'errors': 0,
        'count': 0
    })
    
    # Virtual users over time
    vus_timeline = []
    
    try:
        with open(json_file, 'r') as f:
            line_count = 0
            for line in f:
                line_count += 1
                try:
                    data = json.loads(line.strip())
                    
                    if isinstance(data, dict):
                        # Track virtual users over time
                        if data.get('type') == 'Point' and data.get('metric') == 'vus':
                            point_data = data['data']
                            timestamp = point_data.get('time', '')
                            vus_count = point_data.get('value', 0)
                            vus_timeline.append({
                                'timestamp': timestamp,
                                'vus': vus_count
                            })
                        
                        # Track HTTP request duration
                        elif data.get('type') == 'Point' and data.get('metric') == 'http_req_duration':
                            point_data = data['data']
                            value = point_data.get('value', 0)
                            timestamp = point_data.get('time', '')
                            
                            if value > 0:
                                response_times.append(value)
                                total_requests += 1
                                
                                # Add to timeline
                                timeline_data.append({
                                    'timestamp': timestamp,
                                    'response_time': value,
                                    'tags': point_data.get('tags', {})
                                })
                                
                                # Extract endpoint info from tags or URL
                                tags = point_data.get('tags', {})
                                url = tags.get('url', '')
                                status = tags.get('status', '200')
                                method = tags.get('method', 'GET')
                                name_tag = tags.get('name', '')
                                route_tag = tags.get('route', '')  # K6 route tag we added
                                
                                # Prioritize the route tag from K6
                                if route_tag:
                                    endpoint = route_tag
                                elif endpoint_name := get_endpoint_info_from_config(url, method, routes_config)[0]:
                                    endpoint = endpoint_name  # Use just the route name
                                elif name_tag:
                                    # Fallback to name tag
                                    endpoint = name_tag
                                elif url:
                                    # Fallback to URL parsing
                                    endpoint_parts = url.split('/')
                                    endpoint = f"{method} {endpoint_parts[-1] if endpoint_parts else 'unknown'}"
                                else:
                                    endpoint = 'unknown'
                                
                                endpoint_stats[endpoint]['response_times'].append(value)
                                endpoint_stats[endpoint]['timeline'].append({
                                    'timestamp': timestamp,
                                    'response_time': value
                                })
                                endpoint_stats[endpoint]['count'] += 1
                                
                                if int(status) >= 400:
                                    error_count += 1
                                    endpoint_stats[endpoint]['errors'] += 1
                
                except (json.JSONDecodeError, ValueError, TypeError) as e:
                    continue
    
    except FileNotFoundError:
        print(f"❌ Error: File {json_file} not found")
        return None
    
    print(f"📊 Found {total_requests} requests, {len(timeline_data)} timeline points")
    
    if not response_times:
        print("⚠️ No response time data found.")
        return None
    
    # Calculate statistics
    stats = {
        'total_requests': total_requests,
        'error_count': error_count,
        'error_rate': (error_count / total_requests * 100) if total_requests > 0 else 0,
        'avg_response_time': statistics.mean(response_times),
        'min_response_time': min(response_times),
        'max_response_time': max(response_times),
        'p50_response_time': statistics.median(response_times),
        'p95_response_time': statistics.quantiles(response_times, n=20)[18] if len(response_times) >= 20 else max(response_times),
        'p99_response_time': statistics.quantiles(response_times, n=100)[98] if len(response_times) >= 100 else max(response_times),
        'endpoint_stats': endpoint_stats,
        'timeline_data': timeline_data,
        'vus_timeline': vus_timeline
    }
    
    # Get thresholds from routes config
    thresholds = {}
    if routes_config and 'endpoints' in routes_config:
        for endpoint in routes_config['endpoints']:
            endpoint_name = endpoint.get('name', '')
            
            # Use threshold from config if available, otherwise use defaults
            threshold_ms = endpoint.get('threshold_ms')
            if threshold_ms:
                thresholds[endpoint_name] = threshold_ms
            else:
                # Fallback defaults
                if 'dashboard' in endpoint_name.lower():
                    thresholds[endpoint_name] = 1500
                elif 'student' in endpoint_name.lower() and 'list' in endpoint_name.lower():
                    thresholds[endpoint_name] = 2500
                elif 'student' in endpoint_name.lower() and 'details' in endpoint_name.lower():
                    thresholds[endpoint_name] = 1500
                elif 'course' in endpoint_name.lower():
                    thresholds[endpoint_name] = 5000
                else:
                    thresholds[endpoint_name] = 2000
    
    for endpoint, data in endpoint_stats.items():
        if data['response_times']:
            # Always calculate P95 if we have response times
            p95 = statistics.quantiles(data['response_times'], n=20)[18] if len(data['response_times']) >= 20 else max(data['response_times'])
            data['p95'] = p95
            
            # Set threshold if available
            if endpoint in thresholds:
                data['threshold'] = thresholds[endpoint]
                data['threshold_passed'] = p95 <= thresholds[endpoint]
            else:
                data['threshold'] = None
                data['threshold_passed'] = True
        else:
            data['p95'] = 0
            data['threshold'] = None
            data['threshold_passed'] = True
    
    return stats

def generate_html_report_with_charts(stats, output_file, routes_config=None):
    """Generate HTML report with interactive charts"""
    if not stats:
        print("❌ No stats to generate report from")
        return
    
    # Get report title and subtitle from config
    report_title = "k6 Load Test Report"
    report_subtitle = "Performance testing results"
    
    if routes_config:
        report_title = routes_config.get('report_title', report_title)
        report_subtitle = routes_config.get('report_subtitle', report_subtitle)
    
    # Prepare data for charts
    timeline_labels = []
    timeline_response_times = []
    error_rates = []
    
    # Sort timeline data by timestamp
    sorted_timeline = sorted(stats['timeline_data'], key=lambda x: x['timestamp'])
    
    # Calculate error rates over time by grouping into time windows
    window_size = 50  # Group every 50 requests for error rate calculation
    
    for i, point in enumerate(sorted_timeline):
        if i % 5 == 0:  # Sample every 5th point to avoid overcrowding
            time_obj = datetime.fromisoformat(point['timestamp'].replace('Z', '+00:00'))
            timeline_labels.append(time_obj.strftime('%H:%M:%S'))
            timeline_response_times.append(round(point['response_time'], 2))
            
            # Calculate error rate for this time window
            start_idx = max(0, i - window_size // 2)
            end_idx = min(len(sorted_timeline), i + window_size // 2)
            window_data = sorted_timeline[start_idx:end_idx]
            
            total_in_window = len(window_data)
            errors_in_window = sum(1 for d in window_data if d.get('tags', {}).get('status', '200').startswith(('4', '5')))
            error_rate = (errors_in_window / total_in_window * 100) if total_in_window > 0 else 0
            error_rates.append(round(error_rate, 2))
    
    # VUS timeline - use same sampling as response time for comparison
    vus_labels = []
    vus_values = []
    
    # Create a mapping of timestamps to VUS values for efficient lookup
    vus_map = {}
    for point in stats['vus_timeline']:
        vus_map[point['timestamp']] = point['vus']
    
    # Use the same sampling as response time timeline
    for i, point in enumerate(sorted_timeline):
        if i % 5 == 0:  # Sample every 5th point to match response time sampling
            timestamp = point['timestamp']
            time_obj = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            vus_labels.append(time_obj.strftime('%H:%M:%S'))
            
            # Find the closest VUS value for this timestamp
            closest_vus = 0
            if vus_map:
                # Get the VUS value at this exact timestamp or the closest one
                if timestamp in vus_map:
                    closest_vus = vus_map[timestamp]
                else:
                    # Find the closest timestamp
                    closest_timestamp = min(vus_map.keys(), key=lambda x: abs(datetime.fromisoformat(x.replace('Z', '+00:00')).timestamp() - datetime.fromisoformat(timestamp.replace('Z', '+00:00')).timestamp()))
                    closest_vus = vus_map[closest_timestamp]
            
            vus_values.append(closest_vus)
    
    # Endpoint data for charts
    endpoint_names = []
    endpoint_avg_times = []
    endpoint_counts = []
    endpoint_colors = ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF']
    
    for i, (endpoint, data) in enumerate(stats['endpoint_stats'].items()):
        if data['count'] > 0:
            endpoint_names.append(endpoint)
            endpoint_avg_times.append(round(statistics.mean(data['response_times']), 2))
            endpoint_counts.append(data['count'])
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>k6 Load Test Report with Charts</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 15px; box-shadow: 0 8px 32px rgba(0,0,0,0.1); }}
        h1, h2 {{ color: #333; }}
        h1 {{ text-align: center; margin-bottom: 30px; font-size: 2.5em; }}
        .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 30px 0; }}
        .metric-card {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }}
        .metric-value {{ font-size: 28px; font-weight: bold; margin-bottom: 5px; }}
        .metric-label {{ font-size: 14px; opacity: 0.9; }}
        .chart-container {{ background: #f8f9fa; padding: 20px; border-radius: 10px; margin: 20px 0; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }}
        .chart-title {{ font-size: 18px; font-weight: bold; margin-bottom: 15px; color: #333; text-align: center; }}
        .charts-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 20px 0; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }}
        th, td {{ padding: 15px; text-align: left; }}
        th {{ background: #f8f9fa; font-weight: bold; }}
        tr:nth-child(even) {{ background: #f8f9fa; }}
        .success {{ color: #28a745; font-weight: bold; }}
        .warning {{ color: #ffc107; font-weight: bold; }}
        .danger {{ color: #dc3545; font-weight: bold; }}
        .timestamp {{ text-align: center; color: #666; margin-bottom: 20px; }}
        canvas {{ max-height: 400px; }}
        @media (max-width: 768px) {{
            .charts-grid {{ grid-template-columns: 1fr; }}
            .metrics-grid {{ grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 {report_title}</h1>
        <p class="timestamp">{report_subtitle}</p>
        <p class="timestamp">Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-value">{stats['total_requests']:,}</div>
                <div class="metric-label">Total Requests</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{stats['error_rate']:.1f}%</div>
                <div class="metric-label">Error Rate</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{stats['avg_response_time']:.0f}ms</div>
                <div class="metric-label">Avg Response Time</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{stats['p95_response_time']:.0f}ms</div>
                <div class="metric-label">95th Percentile</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{stats['p99_response_time']:.0f}ms</div>
                <div class="metric-label">99th Percentile</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{max(vus_values) if vus_values else 0}</div>
                <div class="metric-label">Peak Concurrent Users</div>
            </div>
        </div>
        
        <div class="chart-container">
            <div class="chart-title">📈 Response Time Over Time</div>
            <canvas id="responseTimeChart"></canvas>
        </div>
        
        <div class="chart-container">
            <div class="chart-title">👥 Virtual Users Over Time</div>
            <canvas id="vusChart"></canvas>
        </div>
        
        <div class="charts-grid">
            <div class="chart-container">
                <div class="chart-title">🎯 Average Response Time by Endpoint</div>
                <canvas id="endpointChart"></canvas>
            </div>
            <div class="chart-container">
                <div class="chart-title">📊 Request Distribution</div>
                <canvas id="distributionChart"></canvas>
            </div>
        </div>
        
        <div class="charts-grid">
            <div class="chart-container">
                <div class="chart-title">⚡ Response Time Distribution</div>
                <canvas id="histogramChart"></canvas>
            </div>
            <div class="chart-container">
                <div class="chart-title">📊 Error Rate Over Time</div>
                <canvas id="errorRateChart"></canvas>
            </div>
        </div>
        
        <h2>📋 Detailed Endpoint Statistics</h2>
        <table>
            <thead>
                <tr>
                    <th>Endpoint</th>
                    <th>Requests</th>
                    <th>Avg Response Time</th>
                    <th>95th Percentile</th>
                    <th>Threshold</th>
                    <th>Min/Max</th>
                    <th>Success Rate</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
"""
    
    # Add endpoint rows
    for endpoint, data in stats['endpoint_stats'].items():
        if data['count'] > 0:
            success_rate = ((data['count'] - data['errors']) / data['count']) * 100
            avg_time = statistics.mean(data['response_times'])
            min_time = min(data['response_times'])
            max_time = max(data['response_times'])
            p95_time = data.get('p95', 0)
            threshold = data.get('threshold')
            threshold_passed = data.get('threshold_passed', True)
            
            # Determine status based on success rate and threshold compliance
            if success_rate >= 95 and threshold_passed:
                status_class = 'success'
                status_text = '✅ Excellent'
            elif success_rate >= 90 and threshold_passed:
                status_class = 'warning' 
                status_text = '⚠️ Good'
            else:
                status_class = 'danger'
                status_text = '❌ Needs Attention'
            
            # Threshold display
            threshold_display = f"{threshold}ms" if threshold else "N/A"
            threshold_class = 'success' if threshold_passed else 'danger'
            
            html += f"""
                <tr>
                    <td><strong>{endpoint}</strong></td>
                    <td>{data['count']:,}</td>
                    <td>{avg_time:.1f}ms</td>
                    <td class="{threshold_class}">{p95_time:.1f}ms</td>
                    <td>{threshold_display}</td>
                    <td>{min_time:.1f}ms / {max_time:.1f}ms</td>
                    <td class="{status_class}">{success_rate:.1f}%</td>
                    <td class="{status_class}">{status_text}</td>
                </tr>
            """
    
    html += f"""
            </tbody>
        </table>
        
        <div style="text-align: center; margin-top: 40px; color: #666; font-size: 12px;">
            <p>📊 Load Test Report • Generated by k6 </p>
        </div>
    </div>

    <script>
        // Response Time Over Time Chart
        const ctx1 = document.getElementById('responseTimeChart').getContext('2d');
        new Chart(ctx1, {{
            type: 'line',
            data: {{
                labels: {json.dumps(timeline_labels)},
                datasets: [{{
                    label: 'Response Time (ms)',
                    data: {json.dumps(timeline_response_times)},
                    borderColor: '#36A2EB',
                    backgroundColor: 'rgba(54, 162, 235, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    y: {{
                        beginAtZero: true,
                        title: {{
                            display: true,
                            text: 'Response Time (ms)'
                        }}
                    }},
                    x: {{
                        title: {{
                            display: true,
                            text: 'Time'
                        }}
                    }}
                }},
                plugins: {{
                    legend: {{
                        display: true
                    }}
                }}
            }}
        }});

        // Virtual Users Chart - using same timeline as response time for comparison
        const ctx2 = document.getElementById('vusChart').getContext('2d');
        new Chart(ctx2, {{
            type: 'line',
            data: {{
                labels: {json.dumps(timeline_labels)},  // Use same labels as response time
                datasets: [{{
                    label: 'Virtual Users',
                    data: {json.dumps(vus_values)},
                    borderColor: '#FF6384',
                    backgroundColor: 'rgba(255, 99, 132, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,  // Smooth curve
                    pointRadius: 0,  // Remove dots
                    pointHoverRadius: 4  // Show dots only on hover
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    y: {{
                        beginAtZero: true,
                        title: {{
                            display: true,
                            text: 'Virtual Users'
                        }}
                    }},
                    x: {{
                        title: {{
                            display: true,
                            text: 'Time'
                        }}
                    }}
                }},
                plugins: {{
                    legend: {{
                        display: true
                    }}
                }}
            }}
        }});

        // Endpoint Performance Chart
        const ctx3 = document.getElementById('endpointChart').getContext('2d');
        new Chart(ctx3, {{
            type: 'bar',
            data: {{
                labels: {json.dumps(endpoint_names)},
                datasets: [{{
                    label: 'Avg Response Time (ms)',
                    data: {json.dumps(endpoint_avg_times)},
                    backgroundColor: ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF']
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    y: {{
                        beginAtZero: true,
                        title: {{
                            display: true,
                            text: 'Response Time (ms)'
                        }}
                    }}
                }}
            }}
        }});

        // Request Distribution Pie Chart
        const ctx4 = document.getElementById('distributionChart').getContext('2d');
        new Chart(ctx4, {{
            type: 'doughnut',
            data: {{
                labels: {json.dumps(endpoint_names)},
                datasets: [{{
                    data: {json.dumps(endpoint_counts)},
                    backgroundColor: ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF']
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        position: 'bottom'
                    }}
                }}
            }}
        }});

        // Response Time Histogram
        const responseTimes = {json.dumps(stats['timeline_data'])}.map(d => d.response_time);
        const bins = 10;
        const min = Math.min(...responseTimes);
        const max = Math.max(...responseTimes);
        const binSize = (max - min) / bins;
        const histogram = new Array(bins).fill(0);
        const binLabels = [];
        
        for (let i = 0; i < bins; i++) {{
            binLabels.push(`${{Math.round(min + i * binSize)}}-${{Math.round(min + (i + 1) * binSize)}}ms`);
        }}
        
        responseTimes.forEach(time => {{
            const binIndex = Math.min(Math.floor((time - min) / binSize), bins - 1);
            histogram[binIndex]++;
        }});
        
        const ctx5 = document.getElementById('histogramChart').getContext('2d');
        new Chart(ctx5, {{
            type: 'bar',
            data: {{
                labels: binLabels,
                datasets: [{{
                    label: 'Request Count',
                    data: histogram,
                    backgroundColor: '#36A2EB'
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    y: {{
                        beginAtZero: true,
                        title: {{
                            display: true,
                            text: 'Number of Requests'
                        }}
                    }},
                    x: {{
                        title: {{
                            display: true,
                            text: 'Response Time Range'
                        }}
                    }}
                }}
            }}
        }});

        // Error Rate Over Time Chart
        const ctx6 = document.getElementById('errorRateChart').getContext('2d');
        new Chart(ctx6, {{
            type: 'line',
            data: {{
                labels: {json.dumps(timeline_labels)},
                datasets: [{{
                    label: 'Error Rate (%)',
                    data: {json.dumps(error_rates)},
                    borderColor: '#dc3545',
                    backgroundColor: 'rgba(220, 53, 69, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    y: {{
                        beginAtZero: true,
                        max: Math.max(10, Math.max(...{json.dumps(error_rates)})),
                        title: {{
                            display: true,
                            text: 'Error Rate (%)'
                        }}
                    }},
                    x: {{
                        title: {{
                            display: true,
                            text: 'Time'
                        }}
                    }}
                }},
                plugins: {{
                    legend: {{
                        display: true
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""
    
    # Ensure reports directory exists
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w') as f:
        f.write(html)
    
    print(f"✅ Interactive HTML report with charts generated: {output_file}")

def main():
    parser = argparse.ArgumentParser(description='Generate interactive HTML report with charts from k6 JSON results')
    parser.add_argument('json_file', help='k6 JSON results file')
    parser.add_argument('-o', '--output', help='Output HTML file (optional - will use report title from config if not specified)')
    parser.add_argument('-c', '--config', default='endpoints.json', help='Routes configuration file')
    
    args = parser.parse_args()
    
    # Load routes config
    routes_config = load_routes_config(args.config)
    
    # Determine output filename
    if args.output:
        output_file = args.output
    else:
        # Generate filename from report title
        report_title = routes_config.get('report_title', 'k6-load-test-report') if routes_config else 'k6-load-test-report'
        safe_filename = sanitize_filename(report_title)
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        output_file = f"reports/{safe_filename}-{timestamp}.html"
    
    stats = analyze_k6_json_with_timeline(args.json_file, args.config)
    if stats:
        generate_html_report_with_charts(stats, output_file, routes_config)
        
        print(f"\n📊 Test Summary:")
        print(f"   📈 Total Requests: {stats['total_requests']:,}")
        print(f"   ❌ Error Rate: {stats['error_rate']:.1f}%")
        print(f"   ⏱️  Average Response Time: {stats['avg_response_time']:.1f}ms")
        print(f"   📊 95th Percentile: {stats['p95_response_time']:.1f}ms")
        print(f"   👥 Peak Concurrent Users: {max(point['vus'] for point in stats['vus_timeline']) if stats['vus_timeline'] else 0}")
    else:
        print("❌ Could not generate report - no valid data found")

if __name__ == "__main__":
    main()
