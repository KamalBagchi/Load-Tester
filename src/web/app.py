#!/usr/bin/env python3
"""
K6 Load Testing Web Frontend
A Flask web application for uploading endpoints JSON and generating load test reports
"""

import os
import json
import subprocess
import shutil
import tempfile
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, flash, redirect, url_for, send_from_directory
from werkzeug.utils import secure_filename
import uuid
import threading
import time

app = Flask(__name__)
app.secret_key = 'k6-load-testing-secret-key'  # Change this in production
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Configuration
# Get the project root directory (two levels up from src/web/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UPLOAD_FOLDER = os.path.join(PROJECT_ROOT, 'data', 'uploads')
RESULTS_FOLDER = os.path.join(PROJECT_ROOT, 'data', 'results')  
REPORTS_FOLDER = os.path.join(PROJECT_ROOT, 'data', 'reports')
ALLOWED_EXTENSIONS = {'json'}

# Ensure directories exist
for folder in [UPLOAD_FOLDER, RESULTS_FOLDER, REPORTS_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# Store test status in memory (in production, use Redis or database)
test_status = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_endpoints_json(filepath):
    """Validate the uploaded endpoints JSON file"""
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Check required fields
        required_fields = ['base_url', 'endpoints']
        for field in required_fields:
            if field not in data:
                return False, f"Missing required field: {field}"
        
        # Check if endpoints is a list
        if not isinstance(data['endpoints'], list):
            return False, "endpoints must be an array"
        
        # Check if at least one endpoint exists
        if len(data['endpoints']) == 0:
            return False, "At least one endpoint is required"
        
        # Validate each endpoint
        for i, endpoint in enumerate(data['endpoints']):
            required_endpoint_fields = ['name', 'method', 'url']
            for field in required_endpoint_fields:
                if field not in endpoint:
                    return False, f"Endpoint {i+1} missing required field: {field}"
        
        return True, "Valid endpoints JSON file"
    
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON format: {str(e)}"
    except Exception as e:
        return False, f"Error validating file: {str(e)}"

def create_custom_executor(app_dir, test_dir, custom_stages):
    """Create a custom test_executor.js with user-defined stages"""
    
    # Read the original executor file
    original_file = os.path.join(app_dir, '../k6/test_executor.js')
    with open(original_file, 'r') as f:
        content = f.read()
    
    # Convert custom stages to JavaScript format
    stages_js = "[\n"
    for stage in custom_stages:
        stages_js += f"        {{ duration: '{stage['duration']}', target: {stage['target']} }},\n"
    stages_js = stages_js.rstrip(',\n') + "\n          ]"
    
    # Replace the stages configuration in the JavaScript file
    import re
    
    # Find the stages array and replace it - look for the specific stages property
    pattern = r'stages:\s*\[[\s\S]*?\]'
    replacement = f'stages: {stages_js}'
    
    modified_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    # Write the modified content to the test directory
    custom_file = os.path.join(test_dir, 'test_executor.js')
    with open(custom_file, 'w') as f:
        f.write(modified_content)

def run_k6_test(test_id, endpoints_file):
    """Run K6 test in a separate thread"""
    original_cwd = os.getcwd()  # Store original directory at the start
    try:
        test_status[test_id]['status'] = 'running'
        test_status[test_id]['stage'] = 'Preparing test environment'
        
        # Get the directory where the Flask app is located
        app_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Create a temporary directory for this test
        test_dir = os.path.join(RESULTS_FOLDER, test_id)
        os.makedirs(test_dir, exist_ok=True)
        
        # Copy necessary files to test directory
        shutil.copy(endpoints_file, os.path.join(test_dir, 'endpoints.json'))
        shutil.copy(os.path.join(app_dir, '../k6/routes.js'), test_dir)
        shutil.copy(os.path.join(app_dir, '../k6/config_validator.js'), test_dir)
        shutil.copy(os.path.join(app_dir, '../utils/report_generator.py'), test_dir)
        
        # Handle custom stages configuration
        custom_stages = test_status[test_id].get('custom_stages')
        if custom_stages:
            # Create custom test_executor.js with user-defined stages
            create_custom_executor(app_dir, test_dir, custom_stages)
        else:
            # Use default test_executor.js
            shutil.copy(os.path.join(app_dir, '../k6/test_executor.js'), test_dir)
        
        # Change to test directory
        os.chdir(test_dir)
        
        # Create timestamp for unique filenames (only for internal K6 files)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        
        # Extract report title from config
        with open('endpoints.json', 'r') as f:
            config = json.load(f)
        
        report_title = config.get('report_title', 'k6-load-test')
        
        # Improved filename sanitization for clean report name
        import re
        # Remove special characters and normalize
        safe_name = re.sub(r'[^\w\s-]', '', report_title)
        # Replace multiple spaces/hyphens with single hyphen
        safe_name = re.sub(r'[-\s]+', '-', safe_name)
        # Clean up and lowercase
        safe_name = safe_name.strip('-').lower()
        # Remove common redundant words
        safe_name = re.sub(r'\b(report|test|endpoint|api)\b', '', safe_name)
        # Clean up any double hyphens created by word removal
        safe_name = re.sub(r'-+', '-', safe_name).strip('-')
        
        # Fallback if name becomes empty
        if not safe_name:
            safe_name = 'load-test'
        
        # Use timestamp only for internal K6 files to avoid conflicts
        test_name = f"{safe_name}-{timestamp}"
        # Use clean name only for the final report
        clean_report_name = safe_name
        
        test_status[test_id]['stage'] = 'Running K6 load test'
        
        # Run K6 test
        k6_cmd = [
            'k6', 'run',
            f'--summary-export={test_name}_summary.json',
            f'--out=json={test_name}_detailed.json',
            'test_executor.js'
        ]
        
        # --- Live K6 output parsing for stage/VU info ---
        import threading
        import re
        from collections import deque
        
        # Improved regex patterns for K6 output
        # K6 outputs lines like: "     running (1m30s), 342/500 VUs, 12500 complete and 0 interrupted iterations"
        # or: "✓ 342 VUs  1m30s  ████████████████████████████████▌ 90%"
        vus_pattern = re.compile(r"(\d+)/(\d+)\s+VUs")  # Current/Target VUs
        stage_pattern = re.compile(r"running\s+\(([^)]+)\)")  # Running time
        progress_pattern = re.compile(r"(\d+)%")  # Progress percentage
        simple_vus_pattern = re.compile(r"(\d+)\s+VUs")  # Simple VU count
        
        # Start K6 as a subprocess and stream output
        proc = subprocess.Popen(k6_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True)
        
        # For progress tracking
        total_stages = len(custom_stages) if custom_stages else 5  # Default stages count
        current_stage = 1
        current_vus = 0
        target_vus = 0
        progress_percent = 0
        
        # Store last 10 lines for debugging
        last_lines = deque(maxlen=10)
        
        for line in proc.stdout:
            last_lines.append(line)
            line_stripped = line.strip()
            
            # Parse current/target VUs (format: "342/500 VUs")
            vus_match = vus_pattern.search(line)
            if vus_match:
                current_vus = int(vus_match.group(1))
                target_vus = int(vus_match.group(2))
                test_status[test_id]['vus'] = current_vus
                test_status[test_id]['target_vus'] = target_vus
            
            # Parse simple VU count if current/target format not found
            elif simple_vus_pattern.search(line) and 'VUs' in line:
                simple_match = simple_vus_pattern.search(line)
                if simple_match and not vus_match:  # Only use if we didn't find current/target format
                    current_vus = int(simple_match.group(1))
                    test_status[test_id]['vus'] = current_vus
            
            # Parse progress percentage
            progress_match = progress_pattern.search(line)
            if progress_match:
                progress_percent = int(progress_match.group(1))
                test_status[test_id]['progress_percent'] = progress_percent
            
            # Parse running time for stage info
            stage_match = stage_pattern.search(line)
            if stage_match:
                running_time = stage_match.group(1)
                test_status[test_id]['running_time'] = running_time
                test_status[test_id]['stage'] = f"Running for {running_time}"
            
            # Detect stage transitions by looking for specific K6 messages
            if 'ramping up' in line_stripped.lower():
                current_stage += 1
                test_status[test_id]['current_stage'] = current_stage
                test_status[test_id]['total_stages'] = total_stages
                test_status[test_id]['stage'] = f"Stage {current_stage}/{total_stages}: Ramping up"
            elif 'ramping down' in line_stripped.lower():
                test_status[test_id]['stage'] = f"Stage {current_stage}/{total_stages}: Ramping down"
            elif 'staying at' in line_stripped.lower():
                test_status[test_id]['stage'] = f"Stage {current_stage}/{total_stages}: Steady state"
        
        proc.wait(timeout=300)
        exit_code = proc.returncode
        
        # K6 returns exit code 99 when thresholds are crossed, but test completed successfully
        # K6 returns exit code 0 when test completed with all thresholds passed
        # Any other exit code indicates a real failure
        if exit_code != 0 and exit_code != 99:
            test_status[test_id]['status'] = 'failed'
            test_status[test_id]['error'] = f"K6 test failed. Last output: {''.join(last_lines)}"
            return
        
        # Store threshold status for the report
        if exit_code == 99:
            test_status[test_id]['thresholds_crossed'] = True
            test_status[test_id]['warning'] = "Some performance thresholds were exceeded during the test"
        else:
            test_status[test_id]['thresholds_crossed'] = False
        
        test_status[test_id]['stage'] = 'Generating HTML report'
        
        # Ensure the reports directory exists before generating report
        project_root = os.path.dirname(os.path.dirname(app_dir))
        reports_dir = os.path.join(project_root, 'data', 'reports')
        os.makedirs(reports_dir, exist_ok=True)
        
        # Generate HTML report using the Python executable from the virtual environment
        # Get the project root directory (two levels up from src/web/)
        python_executable = os.path.join(project_root, '.venv', 'bin', 'python')
        config_file_path = os.path.join(test_dir, 'endpoints.json')
        report_cmd = [python_executable, 'report_generator.py', f'{test_name}_detailed.json', '-c', config_file_path]
        result = subprocess.run(report_cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0:
            test_status[test_id]['status'] = 'failed'
            test_status[test_id]['error'] = f"Report generation failed: {result.stderr}\nSTDOUT: {result.stdout}"
            return
        
        # Wait a moment for file system to sync
        import time
        time.sleep(1)
        
        # Find the generated HTML report - the report generator outputs to ../../data/reports/
        # Since we've changed directory to test_dir, we need to use absolute paths
        project_root = os.path.dirname(os.path.dirname(app_dir))
        reports_dir = os.path.join(project_root, 'data', 'reports')
        
        html_files = []
        
        # Check the reports directory where the report generator actually outputs files
        if os.path.exists(reports_dir):
            html_files.extend([f for f in os.listdir(reports_dir) if f.endswith('.html')])
            # Sort by modification time to get the most recent
            if html_files:
                html_files.sort(key=lambda x: os.path.getmtime(os.path.join(reports_dir, x)), reverse=True)
        
        # Also check relative path from current directory (where report generator runs)
        relative_reports_dir = "../../data/reports"
        if os.path.exists(relative_reports_dir):
            relative_files = [f for f in os.listdir(relative_reports_dir) if f.endswith('.html')]
            if relative_files and not html_files:  # Use relative files if absolute path didn't work
                html_files = relative_files
                reports_dir = relative_reports_dir  # Update reports_dir for later use
        
        if not html_files:
            # List all files in the directory for debugging
            all_files = os.listdir('.')
            reports_files = os.listdir(reports_dir) if os.path.exists(reports_dir) else []
            test_status[test_id]['status'] = 'failed'
            test_status[test_id]['error'] = f"No HTML report was generated. Files in test directory: {all_files}. Files in reports directory: {reports_files}. Report generation output: {result.stdout}"
            return
        
        # Use the most recent HTML report (should be the one we just generated)
        final_report_name = html_files[0]
        
        # The report is already in the reports directory, so we don't need to move it
        # Just update the test status with the report filename
        
        # Update test status
        test_status[test_id]['status'] = 'completed'
        test_status[test_id]['report_file'] = final_report_name
        test_status[test_id]['summary_file'] = f"{test_name}_summary.json"
        test_status[test_id]['detailed_file'] = f"{test_name}_detailed.json"
        
        # Move result files to web results folder with clean names
        for result_file in [f"{test_name}_summary.json", f"{test_name}_detailed.json"]:
            if os.path.exists(result_file):
                clean_result_name = os.path.basename(result_file)
                shutil.move(result_file, os.path.join(RESULTS_FOLDER, clean_result_name))
        
    except subprocess.TimeoutExpired:
        test_status[test_id]['status'] = 'failed'
        test_status[test_id]['error'] = "Test timed out"
    except Exception as e:
        test_status[test_id]['status'] = 'failed'
        test_status[test_id]['error'] = f"Unexpected error: {str(e)}"
    finally:
        # Change back to original directory
        os.chdir(original_cwd)
        # Clean up test directory
        if 'test_dir' in locals():
            shutil.rmtree(test_dir, ignore_errors=True)




def run_simple_rate_control_test(test_id, endpoints_file):
    """Run simple rate control K6 test - just JSON + rate settings"""
    original_cwd = os.getcwd()
    try:
        test_status[test_id]['status'] = 'running'
        test_status[test_id]['stage'] = 'Preparing simple rate control test'
        
        # Get the directory where the Flask app is located
        app_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Create a temporary directory for this test
        test_dir = os.path.join(RESULTS_FOLDER, test_id)
        os.makedirs(test_dir, exist_ok=True)
        
        # Copy necessary files to test directory
        shutil.copy(endpoints_file, os.path.join(test_dir, 'a.json'))
        shutil.copy(os.path.join(app_dir, '../k6/routes.js'), test_dir)
        shutil.copy(os.path.join(app_dir, '../k6/config_validator.js'), test_dir)
        shutil.copy(os.path.join(app_dir, '../utils/report_generator.py'), test_dir)
        
        # Debug: Log what endpoints file is being used
        print(f"Rate control test using endpoints file: {endpoints_file}")
        with open(endpoints_file, 'r') as f:
            endpoints_content = json.load(f)
        print(f"Endpoints content: {json.dumps(endpoints_content, indent=2)}")
        
        # Copy the simple rate control executor
        shutil.copy(os.path.join(app_dir, '../k6/simple_rate_control_executor.js'), test_dir)
        
        # Change to test directory
        os.chdir(test_dir)
        
        # Create timestamp for unique filenames
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        
        # Get rate configuration
        rate_config = test_status[test_id].get('rate_config', {})
        custom_stages = test_status[test_id].get('custom_stages')
        
        # Extract report title from config
        with open('a.json', 'r') as f:
            config = json.load(f)
        
        report_title = config.get('report_title', 'simple-rate-control-test')
        
        # Clean filename
        import re
        safe_name = re.sub(r'[^\w\s-]', '', report_title)
        safe_name = re.sub(r'[-\s]+', '-', safe_name)
        safe_name = safe_name.strip('-').lower()
        
        if not safe_name:
            safe_name = 'simple-rate-control'
        
        detailed_file = f"{safe_name}-{timestamp}_detailed.json"
        summary_file = f"{safe_name}-{timestamp}_summary.json"
        
        test_status[test_id]['stage'] = 'Configuring rate control parameters'
        
        # Prepare environment variables
        env_vars = os.environ.copy()
        env_vars.update({
            'RATE_TYPE': rate_config.get('rate_type', 'constant'),
            'TARGET_RATE': str(rate_config.get('target_rate', 50)),
            'DURATION': rate_config.get('duration', '5m'),
            'PRE_ALLOCATED_VUS': str(rate_config.get('pre_allocated_vus', 20)),
            'MAX_VUS': str(rate_config.get('max_vus', 200)),
        })
        
        # Add custom stages for ramping mode
        if rate_config.get('rate_type') == 'ramping' and custom_stages:
            env_vars['CUSTOM_STAGES'] = json.dumps(custom_stages)
            if custom_stages:
                env_vars['START_RATE'] = str(custom_stages[0].get('target', 10))
        
        test_status[test_id]['stage'] = f"Running {rate_config.get('rate_type', 'constant')} rate control test at {rate_config.get('target_rate', 50)} RPS"
        
        # Run K6 with simple rate control executor
        cmd = [
            'k6', 'run',
            '--out', f'json={detailed_file}',
            '--summary-export', summary_file,
            'simple_rate_control_executor.js'
        ]
        
        print(f"Running simple rate control: {' '.join(cmd)}")
        
        # Track test progress
        import re
        from collections import deque
        
        vus_pattern = re.compile(r'(\d+)/(\d+)\s+VUs')
        progress_pattern = re.compile(r'(\d+)%')
        stage_pattern = re.compile(r'running \(([^)]+)\)')
        
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env_vars,
            bufsize=1,
            universal_newlines=True
        )
        
        for line in proc.stdout:
            line_stripped = line.strip()
            
            # Parse VUs and progress
            vus_match = vus_pattern.search(line)
            if vus_match:
                current_vus = int(vus_match.group(1))
                target_vus = int(vus_match.group(2))
                test_status[test_id]['vus'] = current_vus
                test_status[test_id]['target_vus'] = target_vus
            
            progress_match = progress_pattern.search(line)
            if progress_match:
                progress_percent = int(progress_match.group(1))
                test_status[test_id]['progress_percent'] = progress_percent
            
            # Update stage information
            stage_match = stage_pattern.search(line)
            if stage_match:
                running_time = stage_match.group(1)
                test_status[test_id]['running_time'] = running_time
                rate_type = rate_config.get('rate_type', 'constant').upper()
                target_rate = rate_config.get('target_rate', 50)
                test_status[test_id]['stage'] = f"{rate_type} Rate Control ({target_rate} RPS) - {running_time}"
        
        proc.wait(timeout=1800)  # 30 minute timeout
        exit_code = proc.returncode
        
        if exit_code in [0, 99]:  # Success or threshold violations
            test_status[test_id]['status'] = 'completed'
            test_status[test_id]['stage'] = 'Generating rate control report'
            
            # Generate HTML report
            try:
                # Ensure the reports directory exists before generating report
                project_root = os.path.dirname(os.path.dirname(app_dir))
                reports_dir = os.path.join(project_root, 'data', 'reports')
                os.makedirs(reports_dir, exist_ok=True)
                
                # Use the same Python executable approach as the standard VU mode
                python_executable = os.path.join(project_root, '.venv', 'bin', 'python')
                config_file_path = os.path.join(os.getcwd(), 'a.json')
                
                # Generate the report with proper paths and config file
                report_cmd = [python_executable, 'report_generator.py', detailed_file, '-c', config_file_path]
                result = subprocess.run(report_cmd, capture_output=True, text=True, timeout=120)
                
                if result.returncode != 0:
                    test_status[test_id]['report_error'] = f"Report generation failed: {result.stderr}\nSTDOUT: {result.stdout}"
                    print(f"Report generation failed: {result.stderr}")
                else:
                    # Wait a moment for file system to sync
                    import time
                    time.sleep(1)
                    
                    # Find the generated HTML report - the report generator outputs to ../../data/reports/
                    html_files = []
                    
                    # Check the reports directory where the report generator actually outputs files
                    if os.path.exists(reports_dir):
                        html_files.extend([f for f in os.listdir(reports_dir) if f.endswith('.html')])
                        # Sort by modification time to get the most recent
                        if html_files:
                            html_files.sort(key=lambda x: os.path.getmtime(os.path.join(reports_dir, x)), reverse=True)
                    
                    # Also check relative path from current directory (where report generator runs)
                    relative_reports_dir = "../../data/reports"
                    if os.path.exists(relative_reports_dir):
                        relative_files = [f for f in os.listdir(relative_reports_dir) if f.endswith('.html')]
                        if relative_files and not html_files:  # Use relative files if absolute path didn't work
                            html_files = relative_files
                            reports_dir = relative_reports_dir  # Update reports_dir for later use
                    
                    if html_files:
                        # Use the most recent HTML report (should be the one we just generated)
                        final_report_name = html_files[0]
                        test_status[test_id]['report_file'] = final_report_name
                    else:
                        # List all files in the directory for debugging
                        all_files = os.listdir('.')
                        reports_files = os.listdir(reports_dir) if os.path.exists(reports_dir) else []
                        test_status[test_id]['report_error'] = f"No HTML report was generated. Files in test directory: {all_files}. Files in reports directory: {reports_files}. Report generation output: {result.stdout}"
                
            except Exception as e:
                print(f"Report generation failed: {e}")
                test_status[test_id]['report_error'] = str(e)
            
            # Move result files
            for result_file in [detailed_file, summary_file]:
                if os.path.exists(result_file):
                    clean_result_name = os.path.basename(result_file)
                    shutil.move(result_file, os.path.join(RESULTS_FOLDER, clean_result_name))
        else:
            test_status[test_id]['status'] = 'failed'
            test_status[test_id]['error'] = f"Simple rate control test failed with exit code {exit_code}"
            
    except subprocess.TimeoutExpired:
        test_status[test_id]['status'] = 'failed'
        test_status[test_id]['error'] = "Simple rate control test timed out"
    except Exception as e:
        test_status[test_id]['status'] = 'failed'
        test_status[test_id]['error'] = f"Unexpected error: {str(e)}"
    finally:
        os.chdir(original_cwd)
        if 'test_dir' in locals():
            shutil.rmtree(test_dir, ignore_errors=True)

@app.route('/')
def index():
    mode = request.args.get('mode', 'standard')
    return render_template('index.html', active_mode=mode)

@app.route('/simple-rate-control')
def simple_rate_control():
    return render_template('index.html', active_mode='rate_control')

@app.route('/upload_simple_rate_control', methods=['POST'])
def upload_simple_rate_control():
    """Handle simple rate control test uploads - JSON file + rate settings OR manual configuration"""
    
    # Check if this is manual configuration FIRST
    is_manual = request.form.get('is_manual') == 'true'
    
    if is_manual:
        # Handle manual configuration - no file upload required
        try:
            # Build the endpoints JSON from form data
            base_url = request.form.get('base_url')
            report_title = request.form.get('report_title', 'Rate Control API Test')
            
            if not base_url:
                flash('Base URL is required')
                return redirect(url_for('index') + '?mode=rate_control')
            
            # Build tokens array
            tokens = []
            token_names = request.form.getlist('token_name[]')
            token_values = request.form.getlist('token_value[]')
            
            for name, value in zip(token_names, token_values):
                if name.strip() and value.strip():
                    tokens.append({
                        'name': name.strip(),
                        'token': value.strip()
                    })
            
            # Build endpoints array
            endpoints = []
            endpoint_names = request.form.getlist('endpoint_name[]')
            endpoint_descriptions = request.form.getlist('endpoint_description[]')
            endpoint_methods = request.form.getlist('endpoint_method[]')
            endpoint_urls = request.form.getlist('endpoint_url[]')
            endpoint_weights = request.form.getlist('endpoint_weight[]')
            endpoint_headers = request.form.getlist('endpoint_headers[]')
            endpoint_bodies = request.form.getlist('endpoint_body[]')
            
            for i, (name, desc, method, url, weight, headers, body) in enumerate(zip(
                endpoint_names, endpoint_descriptions, endpoint_methods, 
                endpoint_urls, endpoint_weights, endpoint_headers, endpoint_bodies
            )):
                if name.strip() and method.strip() and url.strip():
                    endpoint = {
                        'name': name.strip(),
                        'description': desc.strip() if desc.strip() else f"{method} request to {url}",
                        'method': method.strip(),
                        'url': url.strip(),
                        'weight': int(weight) if weight.strip() and weight.isdigit() else 30
                    }
                    
                    # Parse headers JSON
                    if headers.strip():
                        try:
                            endpoint['headers'] = json.loads(headers.strip())
                        except json.JSONDecodeError:
                            endpoint['headers'] = {}
                    else:
                        endpoint['headers'] = {}
                    
                    # Parse body JSON for non-GET requests
                    if body.strip() and method.upper() != 'GET':
                        try:
                            endpoint['body'] = json.loads(body.strip())
                        except json.JSONDecodeError:
                            pass
                    
                    endpoints.append(endpoint)
            
            if not endpoints:
                flash('At least one endpoint is required')
                return redirect(url_for('index') + '?mode=rate_control')
            
            # Create the JSON structure
            endpoints_json = {
                'base_url': base_url,
                'report_title': report_title,
                'tokens': tokens,
                'endpoints': endpoints
            }
            
            # Save to temporary file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_filename = f"manual_rate_control_{timestamp}.json"
            filepath = os.path.join(UPLOAD_FOLDER, temp_filename)
            
            with open(filepath, 'w') as f:
                json.dump(endpoints_json, f, indent=2)
            
            # Debug: Log what was created
            print(f"Manual configuration created: {filepath}")
            print(f"Endpoints JSON: {json.dumps(endpoints_json, indent=2)}")
            
            # Get rate config from manual form
            rate_config = {
                'rate_type': request.form.get('manual_rate_type', 'constant'),
                'target_rate': int(request.form.get('target_rate', 50)),
                'duration': request.form.get('duration', '5m'),
                'pre_allocated_vus': int(request.form.get('pre_allocated_vus', 20)),
                'max_vus': int(request.form.get('max_vus', 200)),
            }
            
            # Validate limits for manual configuration
            rate_config['target_rate'] = min(max(rate_config['target_rate'], 1), 50000)
            rate_config['pre_allocated_vus'] = min(max(rate_config['pre_allocated_vus'], 1), 5000)
            rate_config['max_vus'] = min(max(rate_config['max_vus'], 1), 100000)
            
            # Parse stages for ramping mode
            custom_stages = None
            if rate_config['rate_type'] == 'ramping':
                stage_durations = request.form.getlist('manual_stage_duration[]')
                stage_targets = request.form.getlist('manual_stage_target[]')
                
                if stage_durations and stage_targets and len(stage_durations) == len(stage_targets):
                    valid_stages = []
                    for duration, target in zip(stage_durations, stage_targets):
                        if duration.strip() and target.strip():
                            try:
                                target_int = int(target)
                                valid_stages.append({
                                    'duration': duration.strip(),
                                    'target': target_int
                                })
                            except ValueError:
                                pass
                    
                    if valid_stages:
                        custom_stages = valid_stages
                        
        except Exception as e:
            flash(f'Error processing manual configuration: {str(e)}')
            return redirect(url_for('index') + '?mode=rate_control')
    
    else:
        # Handle file upload mode
        if 'file' not in request.files:
            flash('No file selected')
            return redirect(url_for('index') + '?mode=rate_control')
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected')
            return redirect(url_for('index') + '?mode=rate_control')
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_filename = f"{timestamp}_{filename}"
            filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
            file.save(filepath)
            
            # Validate the uploaded file
            is_valid, message = validate_endpoints_json(filepath)
            if not is_valid:
                os.remove(filepath)
                flash(f'Invalid file: {message}')
                return redirect(url_for('index') + '?mode=rate_control')
        else:
            flash('Invalid file type. Please upload a JSON file.')
            return redirect(url_for('index') + '?mode=rate_control')
    
        # Get rate config from file upload form
        rate_config = {
            'rate_type': request.form.get('rate_type', 'constant'),
            'target_rate': int(request.form.get('target_rate', 50)),
            'duration': request.form.get('duration', '5m'),
            'pre_allocated_vus': int(request.form.get('pre_allocated_vus', 20)),
            'max_vus': int(request.form.get('max_vus', 200)),
        }
        
        # Validate limits for file upload configuration
        rate_config['target_rate'] = min(max(rate_config['target_rate'], 1), 50000)
        rate_config['pre_allocated_vus'] = min(max(rate_config['pre_allocated_vus'], 1), 5000)
        rate_config['max_vus'] = min(max(rate_config['max_vus'], 1), 100000)
        
        # Parse stages for ramping mode
        custom_stages = None
        if rate_config['rate_type'] == 'ramping':
            stage_durations = request.form.getlist('stage_duration[]')
            stage_targets = request.form.getlist('stage_target[]')
            
            if stage_durations and stage_targets and len(stage_durations) == len(stage_targets):
                valid_stages = []
                for duration, target in zip(stage_durations, stage_targets):
                    if duration.strip() and target.strip():
                        try:
                            target_int = int(target)
                            valid_stages.append({
                                'duration': duration.strip(),
                                'target': target_int
                            })
                        except ValueError:
                            pass
                
                if valid_stages:
                    custom_stages = valid_stages
    
    # Generate unique test ID
    test_id = str(uuid.uuid4())
    
    # Get filename for display (different for manual vs file upload)
    if is_manual:
        display_filename = f"manual_rate_control_{timestamp}.json"
    else:
        display_filename = filename
    
    # Initialize test status
    test_status[test_id] = {
        'status': 'queued',
        'stage': 'Initializing Simple Rate Control Test',
        'filename': display_filename,
        'upload_time': datetime.now().isoformat(),
        'test_type': 'simple_rate_control',
        'rate_config': rate_config,
        'custom_stages': custom_stages
    }
    
    # Start simple rate control test
    thread = threading.Thread(target=run_simple_rate_control_test, args=(test_id, filepath))
    thread.daemon = True
    thread.start()
    
    return redirect(url_for('test_status_page', test_id=test_id))

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No file selected')
        return redirect(request.url)
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected')
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_filename = f"{timestamp}_{filename}"
        filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
        file.save(filepath)
        
        # Validate the uploaded file
        is_valid, message = validate_endpoints_json(filepath)
        if not is_valid:
            os.remove(filepath)  # Clean up invalid file
            flash(f'Invalid file: {message}')
            return redirect(url_for('index'))
        
        # Parse custom stages configuration if provided
        custom_stages = None
        stage_durations = request.form.getlist('stage_duration[]')
        stage_targets = request.form.getlist('stage_target[]')
        
        if stage_durations and stage_targets and len(stage_durations) == len(stage_targets):
            # Filter out empty values
            valid_stages = []
            for duration, target in zip(stage_durations, stage_targets):
                if duration.strip() and target.strip():
                    try:
                        target_int = int(target)
                        valid_stages.append({
                            'duration': duration.strip(),
                            'target': target_int
                        })
                    except ValueError:
                        pass  # Skip invalid target values
            
            if valid_stages:
                custom_stages = valid_stages
        
        # Generate unique test ID
        test_id = str(uuid.uuid4())
        
        # Initialize test status
        test_status[test_id] = {
            'status': 'queued',
            'stage': 'Initializing',
            'filename': filename,
            'upload_time': datetime.now().isoformat(),
            'custom_stages': custom_stages
        }
        
        # Start K6 test in background thread
        thread = threading.Thread(target=run_k6_test, args=(test_id, filepath))
        thread.daemon = True
        thread.start()
        
        return redirect(url_for('test_status_page', test_id=test_id))
    
    flash('Invalid file type. Please upload a JSON file.')
    return redirect(url_for('index'))



@app.route('/upload_manual', methods=['POST'])
def upload_manual():
    """Handle manual configuration form submission"""
    try:
        # Build configuration JSON from form data
        config = {
            "base_url": request.form.get('base_url', '').strip(),
            "report_title": request.form.get('report_title', 'Manual Load Test').strip(),
            "report_subtitle": "Load test created from manual configuration",
            "tokens": [],
            "endpoints": []
        }
        
        # Validate required fields
        if not config["base_url"]:
            flash('Base URL is required')
            return redirect(url_for('index'))
        
        # Process tokens
        token_names = request.form.getlist('token_name[]')
        token_values = request.form.getlist('token_value[]')
        
        for name, value in zip(token_names, token_values):
            if name.strip() and value.strip():
                config["tokens"].append({
                    "name": name.strip(),
                    "token": value.strip()
                })
        
        # Process endpoints
        endpoint_names = request.form.getlist('endpoint_name[]')
        endpoint_descriptions = request.form.getlist('endpoint_description[]')
        endpoint_methods = request.form.getlist('endpoint_method[]')
        endpoint_urls = request.form.getlist('endpoint_url[]')
        endpoint_headers = request.form.getlist('endpoint_headers[]')
        endpoint_bodies = request.form.getlist('endpoint_body[]')
        endpoint_weights = request.form.getlist('endpoint_weight[]')
        endpoint_thresholds = request.form.getlist('endpoint_threshold[]')
        endpoint_think_mins = request.form.getlist('endpoint_think_min[]')
        endpoint_think_maxs = request.form.getlist('endpoint_think_max[]')
        
        if not endpoint_names or not any(name.strip() for name in endpoint_names):
            flash('At least one endpoint is required')
            return redirect(url_for('index'))
        
        for i, name in enumerate(endpoint_names):
            if not name.strip():
                continue
                
            endpoint = {
                "name": name.strip(),
                "description": endpoint_descriptions[i].strip() if i < len(endpoint_descriptions) else "",
                "method": endpoint_methods[i] if i < len(endpoint_methods) else "GET",
                "url": endpoint_urls[i].strip() if i < len(endpoint_urls) else "/",
                "headers": {},
                "weight": 30,
                "thinkTime": {"min": 1, "max": 3},
                "threshold_ms": 1000
            }
            
            # Parse headers JSON
            if i < len(endpoint_headers) and endpoint_headers[i].strip():
                try:
                    endpoint["headers"] = json.loads(endpoint_headers[i])
                except json.JSONDecodeError:
                    flash(f'Invalid JSON format in headers for endpoint "{name}"')
                    return redirect(url_for('index'))
            
            # Parse body JSON for POST/PUT/PATCH methods
            if (endpoint["method"] in ["POST", "PUT", "PATCH"] and 
                i < len(endpoint_bodies) and endpoint_bodies[i].strip()):
                try:
                    endpoint["body"] = json.loads(endpoint_bodies[i])
                except json.JSONDecodeError:
                    flash(f'Invalid JSON format in body for endpoint "{name}"')
                    return redirect(url_for('index'))
            
            # Parse numeric values with defaults
            try:
                if i < len(endpoint_weights) and endpoint_weights[i].strip():
                    endpoint["weight"] = int(endpoint_weights[i])
                if i < len(endpoint_thresholds) and endpoint_thresholds[i].strip():
                    endpoint["threshold_ms"] = int(endpoint_thresholds[i])
                if i < len(endpoint_think_mins) and endpoint_think_mins[i].strip():
                    endpoint["thinkTime"]["min"] = int(endpoint_think_mins[i])
                if i < len(endpoint_think_maxs) and endpoint_think_maxs[i].strip():
                    endpoint["thinkTime"]["max"] = int(endpoint_think_maxs[i])
            except ValueError as e:
                flash(f'Invalid numeric value for endpoint "{name}": {str(e)}')
                return redirect(url_for('index'))
            
            config["endpoints"].append(endpoint)
        
        # Parse custom stages configuration if provided
        custom_stages = None
        stage_durations = request.form.getlist('manual_stage_duration[]')
        stage_targets = request.form.getlist('manual_stage_target[]')
        
        if stage_durations and stage_targets and len(stage_durations) == len(stage_targets):
            # Filter out empty values
            valid_stages = []
            for duration, target in zip(stage_durations, stage_targets):
                if duration.strip() and target.strip():
                    try:
                        target_int = int(target)
                        valid_stages.append({
                            'duration': duration.strip(),
                            'target': target_int
                        })
                    except ValueError:
                        pass  # Skip invalid target values
            
            if valid_stages:
                custom_stages = valid_stages
        
        # Save configuration to a temporary JSON file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"manual_config_{timestamp}.json"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        
        with open(filepath, 'w') as f:
            json.dump(config, f, indent=2)
        
        # Validate the generated configuration
        is_valid, message = validate_endpoints_json(filepath)
        if not is_valid:
            os.remove(filepath)  # Clean up invalid file
            flash(f'Configuration validation failed: {message}')
            return redirect(url_for('index'))
        
        # Generate unique test ID
        test_id = str(uuid.uuid4())
        
        # Initialize test status
        test_status[test_id] = {
            'status': 'queued',
            'stage': 'Initializing',
            'filename': f'Manual Configuration ({len(config["endpoints"])} endpoints)',
            'upload_time': datetime.now().isoformat(),
            'custom_stages': custom_stages,
            'config_source': 'manual'
        }
        
        # Start K6 test in background thread
        thread = threading.Thread(target=run_k6_test, args=(test_id, filepath))
        thread.daemon = True
        thread.start()
        
        return redirect(url_for('test_status_page', test_id=test_id))
        
    except Exception as e:
        flash(f'Error processing manual configuration: {str(e)}')
        return redirect(url_for('index'))

@app.route('/test/<test_id>')
def test_status_page(test_id):
    if test_id not in test_status:
        flash('Test not found')
        return redirect(url_for('index'))
    
    return render_template('test_status.html', test_id=test_id)

@app.route('/api/test/<test_id>/status')
def get_test_status(test_id):
    if test_id not in test_status:
        return jsonify({'error': 'Test not found'}), 404
    
    return jsonify(test_status[test_id])

@app.route('/download/report/<test_id>')
def download_report(test_id):
    if test_id not in test_status or test_status[test_id]['status'] != 'completed':
        flash('Report not available')
        return redirect(url_for('index'))
    
    report_file = test_status[test_id]['report_file']
    return send_from_directory(REPORTS_FOLDER, report_file, as_attachment=True)

@app.route('/view/report/<test_id>')
def view_report(test_id):
    if test_id not in test_status or test_status[test_id]['status'] != 'completed':
        flash('Report not available')
        return redirect(url_for('index'))
    
    # Check if report was generated successfully
    if 'report_file' not in test_status[test_id]:
        flash('HTML report was not generated for this test')
        return redirect(url_for('test_status_page', test_id=test_id))
    
    report_file = test_status[test_id]['report_file']
    return send_from_directory(REPORTS_FOLDER, report_file)

@app.route('/download/results/<test_id>/<file_type>')
def download_results(test_id, file_type):
    if test_id not in test_status or test_status[test_id]['status'] != 'completed':
        flash('Results not available')
        return redirect(url_for('index'))
    
    if file_type == 'summary':
        filename = f"{test_id}_{test_status[test_id]['summary_file']}"
    elif file_type == 'detailed':
        filename = f"{test_id}_{test_status[test_id]['detailed_file']}"
    else:
        flash('Invalid file type')
        return redirect(url_for('index'))
    
    return send_from_directory(RESULTS_FOLDER, filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
