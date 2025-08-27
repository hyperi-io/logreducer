#!/bin/bash
# Ensure virtual environment exists and is properly configured
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo -e "${BLUE}=== Ensuring Virtual Environment ===${NC}"
echo "Project root: $PROJECT_ROOT"

# Function to find Python executable
find_python() {
    local required_version="$1"
    local major_minor=$(echo "$required_version" | cut -d. -f1,2)
    
    # Try different Python commands
    for cmd in "python${required_version}" "python${major_minor}" "python3" "python"; do
        if command -v "$cmd" > /dev/null 2>&1; then
            local version=$("$cmd" --version 2>&1 | grep -oP '\d+\.\d+\.\d+' || true)
            if [ -n "$version" ]; then
                local cmd_major_minor=$(echo "$version" | cut -d. -f1,2)
                if [ "$cmd_major_minor" = "$major_minor" ]; then
                    echo "$cmd"
                    return 0
                fi
            fi
        fi
    done
    return 1
}

# Read required Python version
REQUIRED_VERSION="3.12"  # Default
if [ -f ".python-version" ]; then
    REQUIRED_VERSION=$(cat .python-version | tr -d '[:space:]')
    echo -e "${BLUE}Required Python version: $REQUIRED_VERSION${NC}"
fi

# Check if .venv exists and is valid
VENV_VALID=false
if [ -d ".venv" ] && [ -f ".venv/bin/python" ]; then
    VENV_VERSION=$(.venv/bin/python --version 2>&1 | grep -oP '\d+\.\d+' || true)
    REQUIRED_MAJOR_MINOR=$(echo "$REQUIRED_VERSION" | cut -d. -f1,2)
    
    if [ "$VENV_VERSION" = "$REQUIRED_MAJOR_MINOR" ]; then
        echo -e "${GREEN}SUCCESS: .venv exists and uses Python $VENV_VERSION${NC}"
        VENV_VALID=true
    else
        echo -e "${YELLOW}WARNING: .venv uses Python $VENV_VERSION but we need Python $REQUIRED_VERSION${NC}"
        echo -e "${YELLOW}This is a version mismatch - recreating .venv with correct version${NC}"
        echo "Removing old .venv..."
        rm -rf .venv
        echo -e "${BLUE}Will recreate with Python $REQUIRED_VERSION${NC}"
    fi
else
    echo -e "${YELLOW}WARNING: No valid .venv found${NC}"
fi

# Create .venv if needed
if [ "$VENV_VALID" = false ]; then
    echo -e "${BLUE}Creating new virtual environment...${NC}"
    
    # Find appropriate Python
    PYTHON_CMD=$(find_python "$REQUIRED_VERSION")
    if [ -z "$PYTHON_CMD" ]; then
        echo -e "${RED}ERROR: Python $REQUIRED_VERSION not found!${NC}"
        echo "Please install Python $REQUIRED_VERSION first:"
        echo "  - pyenv install $REQUIRED_VERSION"
        echo "  - brew install python@$(echo $REQUIRED_VERSION | cut -d. -f1,2)"
        echo "  - apt install python$REQUIRED_VERSION"
        exit 1
    fi
    
    echo "Using Python: $PYTHON_CMD"
    
    # Try uv first (fastest and most reliable)
    if command -v uv > /dev/null 2>&1; then
        echo "Creating with uv (fastest method)..."
        uv venv .venv --python "$PYTHON_CMD"
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}SUCCESS: Created with uv using Python $REQUIRED_VERSION${NC}"
        else
            echo -e "${YELLOW}WARNING: uv failed, falling back to venv module${NC}"
            "$PYTHON_CMD" -m venv .venv
        fi
    else
        echo "Creating with venv module..."
        "$PYTHON_CMD" -m venv .venv
    fi
    
    if [ ! -f ".venv/bin/activate" ]; then
        echo -e "${RED}ERROR: Failed to create virtual environment!${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}SUCCESS: Virtual environment created${NC}"
fi

# Activate and install dependencies
echo -e "${BLUE}Activating virtual environment...${NC}"
source .venv/bin/activate

# Install basic tools
echo -e "${BLUE}Installing/upgrading pip, setuptools, wheel...${NC}"
python -m pip install --upgrade pip setuptools wheel --quiet

# Install project if pyproject.toml exists
if [ -f "pyproject.toml" ]; then
    echo -e "${BLUE}Installing project dependencies...${NC}"
    if command -v uv > /dev/null 2>&1; then
        uv pip install -e ".[dev,enhanced]"
    else
        pip install -e ".[dev,enhanced]"
    fi
fi

echo ""
# Final verification
FINAL_VERSION=$(.venv/bin/python --version 2>&1 | grep -oP '\d+\.\d+' || true)
REQUIRED_MAJOR_MINOR=$(echo "$REQUIRED_VERSION" | cut -d. -f1,2)

if [ "$FINAL_VERSION" = "$REQUIRED_MAJOR_MINOR" ]; then
    echo -e "${GREEN}=== Virtual Environment Ready ===${NC}"
    echo -e "${GREEN}SUCCESS: Using correct Python version${NC}"
else
    echo -e "${RED}ERROR: Version mismatch after setup!${NC}"
    echo "Expected: Python $REQUIRED_VERSION"
    echo "Got: Python $FINAL_VERSION"
    exit 1
fi

echo "Python: $(which python)"
echo "Version: $(python --version)"
echo ""
echo "To activate manually, run:"
echo "  source .venv/bin/activate"