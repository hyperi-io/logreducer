#!/bin/bash
# Setup virtual environment with correct Python version from .python-version file

set -euo pipefail

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Read Python version from .python-version file
if [ -f ".python-version" ]; then
    REQUIRED_VERSION=$(cat .python-version | tr -d '[:space:]')
    echo -e "${BLUE}READING: Python version from .python-version: ${REQUIRED_VERSION}${NC}"
else
    echo -e "${RED}ERROR: .python-version file not found!${NC}"
    exit 1
fi

# Extract major.minor version
MAJOR_MINOR=$(echo "$REQUIRED_VERSION" | cut -d. -f1,2)

# Check if the required Python version is installed
PYTHON_CMD=""
for cmd in "python${REQUIRED_VERSION}" "python${MAJOR_MINOR}" "python3" "python"; do
    if command -v "$cmd" > /dev/null 2>&1; then
        VERSION=$("$cmd" --version 2>&1 | grep -oP '\d+\.\d+\.\d+' || true)
        if [ -n "$VERSION" ]; then
            CMD_MAJOR_MINOR=$(echo "$VERSION" | cut -d. -f1,2)
            if [ "$CMD_MAJOR_MINOR" = "$MAJOR_MINOR" ]; then
                PYTHON_CMD="$cmd"
                echo -e "${GREEN}FOUND: Python $VERSION at $(which $cmd)${NC}"
                break
            fi
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo -e "${RED}ERROR: Python $REQUIRED_VERSION not found!${NC}"
    echo -e "${YELLOW}Please install Python $REQUIRED_VERSION first.${NC}"
    echo ""
    echo "Options:"
    echo "  1. Using pyenv:"
    echo "     pyenv install $REQUIRED_VERSION"
    echo "     pyenv local $REQUIRED_VERSION"
    echo ""
    echo "  2. Using system package manager:"
    echo "     # Ubuntu/Debian:"
    echo "     sudo apt update && sudo apt install python${MAJOR_MINOR}"
    echo ""
    echo "     # macOS:"
    echo "     brew install python@${MAJOR_MINOR}"
    echo ""
    echo "  3. Download from python.org:"
    echo "     https://www.python.org/downloads/"
    exit 1
fi

# Check if .venv exists and if it uses the correct Python version
if [ -d ".venv" ]; then
    if [ -f ".venv/bin/python" ]; then
        VENV_VERSION=$(.venv/bin/python --version 2>&1 | grep -oP '\d+\.\d+\.\d+' || true)
        VENV_MAJOR_MINOR=$(echo "$VENV_VERSION" | cut -d. -f1,2)
        
        if [ "$VENV_MAJOR_MINOR" != "$MAJOR_MINOR" ]; then
            echo -e "${YELLOW}WARNING: Existing .venv uses Python $VENV_VERSION, but we need $REQUIRED_VERSION${NC}"
            echo -e "${YELLOW}Removing old .venv...${NC}"
            rm -rf .venv
        else
            echo -e "${GREEN}SUCCESS: Existing .venv already uses Python $VENV_VERSION${NC}"
            echo -e "${BLUE}Activating virtual environment...${NC}"
            echo ""
            echo "Run this command to activate:"
            echo "  source .venv/bin/activate"
            exit 0
        fi
    fi
fi

# Create virtual environment with the correct Python version
echo -e "${BLUE}CREATING: Virtual environment with Python $REQUIRED_VERSION...${NC}"

# Try using uv first (fastest)
if command -v uv > /dev/null 2>&1; then
    echo -e "${BLUE}Using uv to create virtual environment...${NC}"
    uv venv .venv --python "$PYTHON_CMD"
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}SUCCESS: Virtual environment created with uv${NC}"
    else
        echo -e "${YELLOW}WARNING: uv failed, falling back to venv module${NC}"
        "$PYTHON_CMD" -m venv .venv
    fi
else
    # Fall back to standard venv
    echo -e "${BLUE}Using venv module to create virtual environment...${NC}"
    "$PYTHON_CMD" -m venv .venv
fi

# Verify the virtual environment
if [ -f ".venv/bin/python" ]; then
    FINAL_VERSION=$(.venv/bin/python --version 2>&1 | grep -oP '\d+\.\d+\.\d+' || true)
    echo -e "${GREEN}SUCCESS: Virtual environment created with Python $FINAL_VERSION${NC}"
    
    # Install basic tools
    echo -e "${BLUE}INSTALLING: pip, setuptools, wheel...${NC}"
    .venv/bin/python -m pip install --upgrade pip setuptools wheel --quiet
    
    echo ""
    echo -e "${GREEN}Virtual environment is ready!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Activate the environment:"
    echo "     source .venv/bin/activate"
    echo ""
    echo "  2. Install project dependencies:"
    echo "     pip install -e '.[dev,enhanced]'"
    echo ""
    echo "  3. Or use uv for faster installation:"
    echo "     uv pip install -e '.[dev,enhanced]'"
else
    echo -e "${RED}ERROR: Failed to create virtual environment!${NC}"
    exit 1
fi