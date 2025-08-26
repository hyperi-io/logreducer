#!/bin/bash
"""
Local CI script for LogReducer development
Run this script to execute the full CI pipeline locally
"""

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to run commands with error handling
run_step() {
    local step_name="$1"
    local command="$2"
    
    print_status "Running: $step_name"
    if eval "$command"; then
        print_success "$step_name completed"
        return 0
    else
        print_error "$step_name failed"
        return 1
    fi
}

# Parse command line arguments
SKIP_SLOW=false
COVERAGE=false
VERBOSE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-slow)
            SKIP_SLOW=true
            shift
            ;;
        --coverage)
            COVERAGE=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --help|-h)
            echo "Local CI Script for LogReducer"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --skip-slow    Skip slow integration tests"
            echo "  --coverage     Generate coverage report"
            echo "  --verbose, -v  Verbose output"
            echo "  --help, -h     Show this help"
            echo ""
            echo "Examples:"
            echo "  $0                    # Run full CI pipeline"
            echo "  $0 --skip-slow       # Skip slow tests"
            echo "  $0 --coverage        # Include coverage report"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Header
echo "=================================================="
echo "🚀 LogReducer Local CI Pipeline"
echo "=================================================="
echo "Skip slow tests: $SKIP_SLOW"
echo "Coverage report: $COVERAGE"
echo "Verbose mode: $VERBOSE"
echo "=================================================="

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ] || [ ! -d "logreducer" ]; then
    print_error "Please run this script from the project root directory"
    exit 1
fi

# Step 1: Environment setup
print_status "Setting up environment"
if [ ! -d ".venv" ]; then
    print_status "Creating virtual environment"
    python -m venv .venv
fi

print_status "Activating virtual environment"
source .venv/bin/activate

# Step 2: Install dependencies
run_step "Installing dependencies" "pip install -e '.[dev,enhanced]'"

# Step 3: Code quality checks
print_status "Running code quality checks"

run_step "Black formatting check" "black --check logreducer/"
run_step "Flake8 linting (critical)" "flake8 logreducer/ --count --select=E9,F63,F7,F82 --show-source --statistics"
run_step "Flake8 linting (all)" "flake8 logreducer/ --count --exit-zero --max-complexity=10 --max-line-length=88 --statistics"

# Type checking (non-blocking)
print_status "Running type checking (non-blocking)"
if mypy logreducer/ 2>/dev/null; then
    print_success "Type checking passed"
else
    print_warning "Type checking found issues (non-blocking)"
fi

# Step 4: Unit tests
PYTEST_ARGS="-v"
if [ "$VERBOSE" = true ]; then
    PYTEST_ARGS="$PYTEST_ARGS -s"
fi

if [ "$COVERAGE" = true ]; then
    PYTEST_ARGS="$PYTEST_ARGS --cov=logreducer --cov-report=term-missing --cov-report=html"
fi

run_step "Unit tests" "pytest tests/unit/ $PYTEST_ARGS"

# Step 5: Integration tests
if [ "$SKIP_SLOW" = true ]; then
    run_step "Integration tests (fast)" "pytest tests/integration/ $PYTEST_ARGS -m 'not slow'"
else
    run_step "Integration tests (all)" "pytest tests/integration/ $PYTEST_ARGS"
fi

# Step 6: Security checks (optional)
print_status "Running security checks"
if command -v safety &> /dev/null; then
    run_step "Dependency vulnerability scan" "safety check"
else
    print_warning "Safety not installed, skipping vulnerability scan"
fi

if command -v bandit &> /dev/null; then
    run_step "Security code scan" "bandit -r logreducer/ -f json -o bandit-report.json || true"
else
    print_warning "Bandit not installed, skipping security scan"
fi

# Step 7: Build test
run_step "Package build test" "python -m build"
run_step "Package validation" "twine check dist/*"

# Step 8: Performance test (basic)
print_status "Running basic performance test"
python -c "
from logreducer import LogReducer
import tempfile
import time

# Create test data
with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
    for i in range(1000):
        f.write(f'2024-01-01 12:00:{i%60:02d} INFO Test log line {i}\n')
    test_file = f.name

# Test performance
start = time.time()
reducer = LogReducer(level='standard')
result = reducer.process_file(test_file)
duration = time.time() - start

print(f'✅ Performance test: Processed 1000 lines in {duration:.2f}s')
print(f'   Reduced to {len(result)} representative lines')

import os
os.unlink(test_file)
"

# Summary
echo "=================================================="
print_success "Local CI Pipeline Completed Successfully!"
echo "=================================================="

if [ "$COVERAGE" = true ] && [ -d "htmlcov" ]; then
    print_status "Coverage report generated in htmlcov/"
fi

if [ -d "dist" ]; then
    print_status "Build artifacts:"
    ls -la dist/
fi

echo ""
print_status "Next steps:"
echo "  - Review any warnings above"
echo "  - Run 'git add .' and 'git commit' with conventional commit format"
echo "  - Push to trigger full CI/CD pipeline"
echo ""