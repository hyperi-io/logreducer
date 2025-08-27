#!/bin/bash
# Setup GitHub Actions self-hosted runner with local dev environment
set -euo pipefail

# Configuration
RUNNER_NAME="${RUNNER_NAME:-logreducer-local}"
RUNNER_LABELS="${RUNNER_LABELS:-self-hosted,linux,x64,local-dev}"
RUNNER_WORK_DIR="${RUNNER_WORK_DIR:-_work}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== GitHub Actions Self-Hosted Runner Setup ===${NC}"
echo ""

# Check if we're in the logreducer project
if [ ! -f "pyproject.toml" ] || [ ! -d "src/logreducer" ]; then
    echo -e "${RED}ERROR: Run this script from the logreducer project root${NC}"
    exit 1
fi

PROJECT_ROOT=$(pwd)
echo -e "${GREEN}Project root: $PROJECT_ROOT${NC}"

# Create runner directory
RUNNER_DIR="$HOME/.github-runner"
mkdir -p "$RUNNER_DIR"

# Download runner if not already present
if [ ! -f "$RUNNER_DIR/config.sh" ]; then
    echo -e "${BLUE}Downloading GitHub Actions runner...${NC}"
    cd "$RUNNER_DIR"
    
    # Get latest runner version
    RUNNER_VERSION=$(curl -s https://api.github.com/repos/actions/runner/releases/latest | grep tag_name | cut -d '"' -f 4 | sed 's/v//')
    echo "Latest runner version: $RUNNER_VERSION"
    
    # Download and extract
    curl -o actions-runner-linux-x64.tar.gz -L "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz"
    tar xzf ./actions-runner-linux-x64.tar.gz
    rm actions-runner-linux-x64.tar.gz
else
    echo -e "${YELLOW}Runner already downloaded${NC}"
    cd "$RUNNER_DIR"
fi

# Create runner environment setup script
cat > "$RUNNER_DIR/setup_env.sh" << 'EOF'
#!/bin/bash
# This script is sourced before each job to set up the environment

# Detect project root (where this runner will execute jobs)
if [ -n "$GITHUB_WORKSPACE" ]; then
    PROJECT_ROOT="$GITHUB_WORKSPACE"
elif [ -f "$PWD/pyproject.toml" ]; then
    PROJECT_ROOT="$PWD"
else
    PROJECT_ROOT="/projects/logreducer"
fi

echo "Setting up environment for: $PROJECT_ROOT"

# Use project's Python virtual environment if it exists
if [ -d "$PROJECT_ROOT/.venv" ]; then
    echo "Activating project virtual environment"
    source "$PROJECT_ROOT/.venv/bin/activate"
    export PATH="$PROJECT_ROOT/.venv/bin:$PATH"
fi

# Use project's .python-version if it exists
if [ -f "$PROJECT_ROOT/.python-version" ]; then
    PYTHON_VERSION=$(cat "$PROJECT_ROOT/.python-version" | tr -d '[:space:]')
    echo "Project requires Python $PYTHON_VERSION"
    
    # Try to use pyenv if available
    if command -v pyenv > /dev/null 2>&1; then
        pyenv local "$PYTHON_VERSION" 2>/dev/null || true
    fi
fi

# Add uv to PATH if installed
if [ -d "$HOME/.cargo/bin" ]; then
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# Set project-specific temp directory
export TMPDIR="$PROJECT_ROOT/.tmp"
export TEMP="$PROJECT_ROOT/.tmp"
export TMP="$PROJECT_ROOT/.tmp"
mkdir -p "$TMPDIR"

# Node.js setup for semantic-release
if command -v nvm > /dev/null 2>&1; then
    nvm use 20 2>/dev/null || nvm use stable 2>/dev/null || true
fi

# Python path configuration
export PYTHONPATH="$PROJECT_ROOT/src:$PYTHONPATH"

# Enable color output
export FORCE_COLOR=1
export PY_COLORS=1

echo "Environment setup complete"
EOF

chmod +x "$RUNNER_DIR/setup_env.sh"

# Create runner service wrapper that uses our environment
cat > "$RUNNER_DIR/run_with_env.sh" << 'EOF'
#!/bin/bash
# Wrapper script to run GitHub Actions with project environment

RUNNER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source our environment setup
source "$RUNNER_DIR/setup_env.sh"

# Run the actual runner
exec "$RUNNER_DIR/run.sh" "$@"
EOF

chmod +x "$RUNNER_DIR/run_with_env.sh"

# Create systemd service file for automatic startup
cat > "$RUNNER_DIR/github-runner.service" << EOF
[Unit]
Description=GitHub Actions Runner for LogReducer
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$RUNNER_DIR
ExecStart=$RUNNER_DIR/run_with_env.sh
Restart=always
RestartSec=10
KillMode=process
KillSignal=SIGTERM
TimeoutStopSec=5min

# Environment variables
Environment="PATH=$HOME/.cargo/bin:/usr/local/bin:/usr/bin:/bin"
Environment="HOME=$HOME"
Environment="USER=$USER"

[Install]
WantedBy=multi-user.target
EOF

echo ""
echo -e "${BLUE}=== Configuration Instructions ===${NC}"
echo ""
echo "1. Go to: https://github.com/hypersec-io/logreducer/settings/actions/runners"
echo ""
echo "2. Click 'New self-hosted runner' and copy the token"
echo ""
echo "3. Run this command with your token:"
echo -e "${GREEN}cd $RUNNER_DIR${NC}"
echo -e "${GREEN}./config.sh --url https://github.com/hypersec-io/logreducer --token YOUR_TOKEN_HERE --name $RUNNER_NAME --labels $RUNNER_LABELS --work $RUNNER_WORK_DIR${NC}"
echo ""
echo "4. To install as a system service (auto-start on boot):"
echo -e "${GREEN}sudo cp $RUNNER_DIR/github-runner.service /etc/systemd/system/${NC}"
echo -e "${GREEN}sudo systemctl daemon-reload${NC}"
echo -e "${GREEN}sudo systemctl enable github-runner${NC}"
echo -e "${GREEN}sudo systemctl start github-runner${NC}"
echo ""
echo "5. Or run interactively for testing:"
echo -e "${GREEN}cd $RUNNER_DIR && ./run_with_env.sh${NC}"
echo ""
echo -e "${YELLOW}Note: The runner will automatically:${NC}"
echo "  - Use the project's .venv if it exists"
echo "  - Read .python-version for Python version"
echo "  - Set up proper PYTHONPATH"
echo "  - Use project's .tmp directory"
echo "  - Activate uv if installed"