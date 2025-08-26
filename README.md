# 🚀 K6 Load Testing Tool

A comprehensive web-based load testing platform built with K6, Flask, and modern web technologies. Features standard Virtual User Control and Simple Rate Control modes for effective performance testing with detailed interactive reports.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![K6](https://img.shields.io/badge/K6-Load%20Testing-orange.svg)](https://k6.io/)
[![Flask](https://img.shields.io/badge/Flask-2.3+-green.svg)](https://flask.palletsprojects.com/)

## ✨ Features

### 🌐 **Web-Based Interface**
- Intuitive drag-and-drop file upload
- Real-time test progress monitoring
- Configuration options with expandable UI
- Responsive design for all devices

### 📊 **Interactive Reports**
- **Chart.js powered visualizations**: Response time trends, throughput charts, error rate graphs
- **Detailed analytics**: 95th percentile, peak users, timeline analysis
- **Export capabilities**: HTML reports with embedded charts and raw JSON data
- **Performance insights**: Endpoint-specific metrics and recommendations

### ⚡ **Load Testing Capabilities**
- **Dual Testing Methods**: Virtual User Control and Simple Rate Control
- **Custom test stages**: Configure ramp-up, steady state, and ramp-down phases
- **Multiple authentication**: Support for different user types with token rotation
- **Weighted endpoints**: Realistic traffic distribution across API endpoints
- **Think time simulation**: Configurable delays between requests
- **Rate control**: Basic requests-per-second targeting for capacity planning

### 🔧 **Flexible Configuration**
- **JSON-based setup**: Easy endpoint configuration with validation
- **Multi-environment support**: Test staging, production, or development APIs
- **Header customization**: Custom headers, authorization tokens, content types
- **Request body templates**: Support for GET, POST, PUT, DELETE methods

### 📈 **Performance Monitoring**
- **Real-time status updates**: Live progress tracking and stage monitoring
- **Error detection**: Automatic error rate calculation and threshold alerts
- **Timeline analysis**: Request-by-request performance breakdown
- **Concurrent user tracking**: Monitor virtual user load patterns

## 🏗️ Project Architecture

```
K6-Load-Testing/
├── 📁 data/                    # Data storage and results
│   ├── 📤 uploads/            # User uploaded test configurations
│   ├── 📊 results/            # Raw K6 test results (JSON)
│   └── 📋 reports/            # Generated HTML reports with charts
├── 📁 scripts/                # Automation and utility scripts
│   ├── 🚀 run_tests.sh       # Standard test execution with specific endpoints
│   ├── ⚡ quick_test.sh       # Quick test with latest uploaded file
│   └── 🖥️  start_server.sh    # Web server with auto-restart and validation
├── 📁 src/                    # Source code and application logic
│   ├── 📁 k6/                # K6 JavaScript test modules
│   │   ├── ⚙️ test_executor.js    # Main K6 test runner with stages
│   │   ├── 🛣️ routes.js          # Route management and token handling
│   │   └── ✅ config_validator.js # JSON configuration validation
│   ├── 📁 utils/              # Python utility modules
│   │   └── 📈 report_generator.py # HTML report with Chart.js integration
│   └── 📁 web/               # Flask web application
│       ├── 🌐 app.py          # Main Flask server with upload handling
│       ├── 📁 routes/         # API route handlers
│       ├── 📁 static/         # CSS, JavaScript, and assets
│       │   ├── 🎨 css/        # Custom styling and themes
│       │   └── ⚡ js/         # Frontend JavaScript logic
│       └── 📁 templates/      # Jinja2 HTML templates
│           ├── 🏠 base.html        # Base template with Bootstrap
│           ├── 📤 index.html       # Main upload and configuration page
│           └── 📊 test_status.html # Real-time test monitoring
├── 📄 requirements.txt        # Python dependencies
├── 📜 LICENSE                 # MIT License
└── 📖 README.md              # This documentation
```

## 🚀 Quick Start Guide

### Prerequisites

- **Python 3.8+** with pip
- **K6** load testing tool ([Download K6](https://k6.io/docs/getting-started/installation/))
- **Modern web browser** (Chrome, Firefox, Safari, Edge)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/KamalBagchi/Load-Tester.git
   cd K6-Load-Testing
   ```

2. **Set up Python virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Verify K6 installation**
   ```bash
   k6 version
   ```

## 🎯 Getting Started

### Quick Start (3 Steps)

1. **🚀 Start the Frontend**
   ```bash
   ./scripts/start_server.sh
   ```
   This will:
   - ✅ Validate all dependencies (Python, K6, pip)
   - ✅ Create virtual environment if needed
   - ✅ Install Python packages
   - ✅ Create required directories
   - ✅ Start Flask web server at **http://localhost:5000**

2. **🌐 Open Web Interface**
   ```bash
   # Open in your browser:
   http://localhost:5000
   ```
   You'll see a modern web interface with:
   - 📤 Drag & drop file upload
   - ⚙️ Test configuration options
   - 📊 Real-time test monitoring

3. **🧪 Run Your First Test**
   - **Upload** your `endpoints.json` file via the web interface
   - **Configure** test stages (optional - defaults provided)
   - **Click** "Start Load Test" button
   - **Monitor** real-time progress
   - **View** interactive HTML reports with charts

### Alternative: Command Line Testing

If you prefer command line or have existing endpoint files:

```bash
# Virtual User Control (VU-based) - Traditional load testing
./scripts/quick_test.sh
./scripts/run_tests.sh data/uploads/your-endpoints.json

# Request Rate Control (RPS-based) - Capacity testing
./scripts/run_rate_control.sh --type constant --rate 50 --duration 5m
./scripts/run_rate_control.sh --type ramping --max-vus 500
```

## 📋 Detailed Usage

### 🎯 Usage

#### Method 1: Web Interface (Recommended)

1. **Start the web server**
   ```bash
   ./scripts/start_server.sh
   # Or manually: cd src/web && python app.py
   ```

2. **Access the application**
   - Open [http://localhost:5000](http://localhost:5000) in your browser
   - The interface will load with Bootstrap styling and interactive elements

3. **Configure your test**
   - **Upload**: Drag and drop your `endpoints.json` file
   - **Configuration Settings**: Click "Show Advanced" to configure custom test stages
   - **Test Stages**: Set duration and target users for each phase
     - Stage 1: `1m` → `0 users` (Initialization)
     - Stage 2: `10s` → `10 users` (Ramp-up)
     - Stage 3: `40s` → `10 users` (Steady state)
     - Stage 4: `10s` → `0 users` (Ramp-down)
     - Stage 5: `2m` → `0 users` (Cool-down)

4. **Monitor and analyze**
   - Real-time progress updates during test execution
   - Automatic report generation with interactive charts
   - Download detailed HTML reports for further analysis

#### Method 2: Command Line

**Virtual User Control (Traditional)**
```bash
# Quick test with latest uploaded endpoints file
./scripts/quick_test.sh

# Run test with specific endpoints file
./scripts/run_tests.sh data/uploads/your-endpoints.json
```

**Request Rate Control (Capacity Testing)**
```bash
# Constant rate testing
./scripts/run_rate_control.sh --type constant --rate 50 --duration 5m
./scripts/run_rate_control.sh --rate 100 --duration 10m --max-vus 300

# Ramping rate testing
./scripts/run_rate_control.sh --type ramping --max-vus 500

# View help for more options
./scripts/run_rate_control.sh --help
```

**Report Generation**
```bash
# Generate reports from existing results
python src/utils/report_generator.py data/results/your-test-results.json

# Start the web server manually
./scripts/start_server.sh
```

## 🎯 Testing Methods

This platform supports **two distinct load testing approaches** to meet different testing objectives:

### 1. Virtual User Control (VU-based) 
**Best for**: User experience testing, realistic user behavior simulation
- Controls the number of **virtual users** making requests
- Each user follows realistic patterns with think times
- Request rate varies based on system performance
- More realistic user simulation

### 2. Request Rate Control (RPS-based)
**Best for**: Capacity planning, SLA validation, API throughput testing  
- Controls **requests per second** directly
- K6 automatically scales virtual users to maintain target rate
- Consistent load regardless of response times
- Perfect for capacity and performance testing

| Method | Controls | Request Rate | Best For |
|--------|----------|--------------|----------|
| Virtual User | # of Users | Variable | User Experience |
| Rate Control | Requests/sec | Fixed | Capacity Planning |

📚 **Detailed comparison**: See [docs/TESTING_METHODS.md](docs/TESTING_METHODS.md)

## 📋 Configuration Format

### Endpoints Configuration (`endpoints.json`)

```json
{
  "base_url": "https://api.example.com",
  "report_title": "API Performance Test",
  "report_subtitle": "Load testing for production endpoints",
  "tokens": [
    {
      "token": "eyJhbGciOiJIUzI1NiIs...",
      "name": "ADMIN_TOKEN"
    },
    {
      "token": "eyJhbGciOiJIUzI1NiIs...",
      "name": "USER_TOKEN"
    }
  ],
  "endpoints": [
    {
      "name": "USER_LOGIN",
      "description": "User authentication endpoint",
      "method": "POST",
      "url": "/api/v1/auth/login",
      "body": {
        "email": "test@example.com",
        "password": "testpass123"
      },
      "headers": {
        "Content-Type": "application/json",
        "Authorization": "<USER_TOKEN>"
      },
      "weight": 30,
      "thinkTime": {
        "min": 1,
        "max": 3
      },
      "threshold_ms": 1000
    }
  ]
}
```

### Configuration Options

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `base_url` | String | API base URL | `"https://api.example.com"` |
| `report_title` | String | Report title | `"API Performance Test"` |
| `report_subtitle` | String | Report description | `"Production load testing"` |
| `tokens` | Array | Authentication tokens | `[{"token": "...", "name": "USER_TOKEN"}]` |
| `endpoints` | Array | Test endpoints | See endpoint configuration below |

### Endpoint Configuration

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | String | ✅ | Unique endpoint identifier |
| `description` | String | ❌ | Human-readable description |
| `method` | String | ✅ | HTTP method (`GET`, `POST`, `PUT`, `DELETE`) |
| `url` | String | ✅ | Endpoint path (relative to `base_url`) |
| `body` | Object/null | ❌ | Request body for POST/PUT requests |
| `headers` | Object | ❌ | Custom headers (use `<TOKEN_NAME>` for token substitution) |
| `weight` | Number | ❌ | Request frequency weight (default: 10) |
| `thinkTime` | Object | ❌ | Delay between requests `{"min": 1, "max": 5}` |
| `threshold_ms` | Number | ❌ | Performance threshold in milliseconds |

## 📊 Report Features

### Interactive Charts
- **Response Time Trends**: Timeline visualization of response times
- **Throughput Analysis**: Requests per second over time
- **Error Rate Monitoring**: Success/failure ratio tracking
- **Percentile Analysis**: 95th percentile response time distribution

### Detailed Metrics
- **Test Summary**: Total requests, error rate, average response time
- **Peak Performance**: Maximum concurrent users and throughput
- **Endpoint Analysis**: Per-endpoint performance breakdown
- **Timeline Data**: Request-by-request performance logs

### Export Options
- **HTML Reports**: Self-contained files with embedded charts
- **JSON Data**: Raw test results for further analysis
- **Performance Insights**: Automated recommendations and alerts

## � Automation Scripts

The project includes three powerful automation scripts located in the `scripts/` directory:

### 🚀 **`run_tests.sh`** - Standard Test Execution

**Purpose**: Execute K6 load tests with specific endpoint configurations and generate comprehensive reports.

**Usage**:
```bash
./scripts/run_tests.sh <endpoints-file.json>
```

**Features**:
- ✅ **Parameter validation**: Requires specific endpoints file
- ✅ **File existence check**: Validates file before execution
- ✅ **Automatic report generation**: Creates HTML reports with charts
- ✅ **Clean file handling**: Copies and cleans up temporary files
- ✅ **Detailed feedback**: Shows progress and completion status

**Example**:
```bash
# Run test with specific configuration
./scripts/run_tests.sh data/uploads/20250808_120143_endpoints.json

# Output:
# 🚀 Starting k6 load test with comprehensive reporting...
# 📊 Running k6 test with: 20250808_120143_endpoints.json
# 📈 Generating HTML report with interactive charts...
# ✅ Test completed! Generated files: ...
```

### ⚡ **`quick_test.sh`** - Instant Testing

**Purpose**: Quickly run tests using the most recently uploaded endpoints file.

**Usage**:
```bash
./scripts/quick_test.sh
```

**Features**:
- ✅ **Auto-discovery**: Finds the latest uploaded endpoints file
- ✅ **Smart validation**: Checks if upload directory exists and has files
- ✅ **File information**: Shows which file is being used and when it was uploaded
- ✅ **Zero configuration**: No parameters needed - just run and go

**Example**:
```bash
# Quick test with latest file
./scripts/quick_test.sh

# Output:
# 🚀 Quick K6 Load Test Runner
# 📁 Using latest endpoints file: my-api-endpoints.json
# ⏰ File uploaded: 2025-08-08 12:32:28
# 🚀 Starting k6 load test...
```

### 🖥️ **`start_server.sh`** - Web Server Management

**Purpose**: Set up and start the Flask web server with comprehensive environment validation.

**Usage**:
```bash
./scripts/start_server.sh
```

**Features**:
- ✅ **Dependency validation**: Checks Python 3, pip3, and K6 installation
- ✅ **Environment setup**: Creates virtual environment if needed
- ✅ **Package management**: Installs/updates Python dependencies
- ✅ **Directory structure**: Creates required data directories
- ✅ **Permission handling**: Sets proper file permissions
- ✅ **Helpful errors**: Provides installation instructions for missing dependencies

**Example**:
```bash
# Start the web server
./scripts/start_server.sh

# Output:
# 🚀 Starting K6 Load Testing Web Interface...
# 🔧 Activating virtual environment...
# 📚 Installing/upgrading dependencies...
# 📁 Creating directory structure...
# ✅ Setup complete!
# 🌐 Starting web server...
```

### 📋 **Script Dependencies**

| Script | Requirements | Auto-Install |
|--------|-------------|--------------|
| `run_tests.sh` | K6, Python 3, endpoints file | ❌ Manual K6 install |
| `quick_test.sh` | K6, Python 3, uploaded files | ❌ Manual K6 install |
| `start_server.sh` | Python 3, pip3, K6 | ✅ Python packages only |

### 🔄 **Script Workflow**

**Typical Usage Flow:**
```
1. 🖥️  start_server.sh          → Start web interface
2. 🌐 Web Interface             → Upload endpoints.json file  
3. ⚡ quick_test.sh             → Quick test with latest file
   OR
   🚀 run_tests.sh <file>       → Test with specific file
4. 📊 K6 Test Execution         → Load testing in progress
5. 📈 HTML Report Generation    → Interactive charts created
6. 👀 View Results             → Analyze performance data
```

**Script Relationships:**
- **`start_server.sh`** enables the web interface for file uploads
- **`quick_test.sh`** automatically finds and tests the latest uploaded file
- **`run_tests.sh`** provides control over which specific file to test
- All scripts generate comprehensive HTML reports with interactive charts

### 🛠️ **Script Customization**

All scripts support customization through environment variables:

```bash
# Custom K6 options
export K6_OPTIONS="--vus 100 --duration 5m"
./scripts/run_tests.sh data/uploads/endpoints.json

# Custom Python executable
export PYTHON_CMD="python3.11"
./scripts/start_server.sh

# Custom output directory
export RESULTS_DIR="custom-results"
./scripts/quick_test.sh
```

## �🛠️ Development

### Technology Stack
- **Backend**: Python 3.8+ with Flask 2.3+
- **Frontend**: Bootstrap 5, Chart.js, Vanilla JavaScript
- **Load Testing**: K6 with JavaScript test scripts
- **Reports**: Python with Chart.js integration
- **Data Storage**: JSON files with structured organization

### Development Setup

1. **Install development dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run in development mode**
   ```bash
   cd src/web
   export FLASK_ENV=development
   python app.py
   ```

3. **File watching for auto-reload**
   ```bash
   # The Flask app supports auto-reload in development mode
   python app.py --debug
   ```

### Project Components

#### Flask Web Application (`src/web/`)
- **`app.py`**: Main Flask server with file upload, test execution, and status monitoring
- **`templates/`**: Jinja2 templates with Bootstrap styling and interactive JavaScript
- **`static/`**: CSS styling and frontend JavaScript for enhanced user experience

#### K6 Test Scripts (`src/k6/`)
- **`test_executor.js`**: Main K6 script with configurable stages and metrics
- **`routes.js`**: Route management with weighted distribution and token rotation
- **`config_validator.js`**: JSON schema validation for endpoint configurations

#### Report Generation (`src/utils/`)
- **`report_generator.py`**: HTML report generation with Chart.js integration
- Supports timeline analysis, performance metrics, and interactive visualizations

## 🤝 Contributing

1. **Fork the repository**
2. **Create a feature branch** (`git checkout -b feature/amazing-feature`)
3. **Commit your changes** (`git commit -m 'Add amazing feature'`)
4. **Push to the branch** (`git push origin feature/amazing-feature`)
5. **Open a Pull Request**

### Development Guidelines
- Follow Python PEP 8 styling guidelines
- Add comprehensive tests for new features
- Update documentation for API changes
- Ensure backward compatibility

## 📝 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

### MIT License Summary
- ✅ Commercial use
- ✅ Modification
- ✅ Distribution
- ✅ Private use
- ❌ Liability
- ❌ Warranty

## 🆘 Support & Troubleshooting

### Common Issues

**Q: "FileNotFoundError" when uploading files**
- **Solution**: Ensure the `data/uploads/` directory exists and has write permissions
- **Script Check**: Run `./scripts/start_server.sh` to create required directories

**Q: K6 tests not running**
- **Solution**: Verify K6 is installed and accessible in your PATH (`k6 version`)
- **Installation**: Follow instructions from `./scripts/start_server.sh` error messages

**Q: Reports not generating**
- **Solution**: Check Python dependencies are installed (`pip list | grep Flask`)
- **Quick Fix**: Run `./scripts/start_server.sh` to install/update dependencies

**Q: Custom stages not applying**
- **Solution**: Ensure you're using the web interface configuration settings to configure stages
- **Alternative**: Use `./scripts/run_tests.sh` with properly configured endpoints file

**Q: Script permission denied**
- **Solution**: Make scripts executable: `chmod +x scripts/*.sh`
- **Verification**: Check with `ls -la scripts/`

**Q: "No endpoint files found" error**
- **Solution**: Upload endpoints.json through web interface first
- **Check**: Verify files exist with `ls data/uploads/*.json`

**Q: Virtual environment issues**
- **Solution**: Remove `.venv` directory and run `./scripts/start_server.sh` again
- **Manual Fix**: `rm -rf .venv && python3 -m venv .venv`

### Script-Specific Troubleshooting

| Script | Common Issue | Solution |
|--------|-------------|----------|
| `quick_test.sh` | "No endpoint files found" | Upload files via web interface first |
| `run_tests.sh` | "Usage: ./scripts/run_tests.sh <file>" | Provide specific endpoints file path |
| `start_server.sh` | "Python 3 is required" | Install Python 3.8+ from python.org |
| All scripts | "Permission denied" | Run `chmod +x scripts/*.sh` |

### Getting Help

- **Issues**: [GitHub Issues](https://github.com/KamalBagchi/Load-Tester/issues)
- **Documentation**: Check this README and inline code comments
- **K6 Documentation**: [Official K6 Docs](https://k6.io/docs/)

---

**Made with ❤️ by [Kamal Nayan Bagchi](https://github.com/KamalBagchi)**
