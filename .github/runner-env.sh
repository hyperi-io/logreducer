#!/bin/bash
# GitHub Actions Runner Environment Auto-Detection
# This file is sourced by the runner to set up the local dev environment

echo "Auto-detecting local development environment..."

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

# Detect if we're in a Git repository
if [ -d ".git" ] || git rev-parse --git-dir > /dev/null 2>&1; then
    PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
else
    PROJECT_ROOT=$(pwd)
fi

echo "? Project root: $PROJECT_ROOT"
cd "$PROJECT_ROOT"

# Check for .python-version file
if [ -f ".python-version" ]; then
    REQUIRED_PYTHON=$(cat .python-version | tr -d '[:space:]')
    echo "? Required Python version: $REQUIRED_PYTHON"
    
    # Check for pyenv
    if command -v pyenv > /dev/null 2>&1; then
        echo "[PKG] Using pyenv to set Python version"
        pyenv local "$REQUIRED_PYTHON" 2>/dev/null || {
            echo "[WARN]  Python $REQUIRED_PYTHON not installed in pyenv"
            echo "   Run: pyenv install $REQUIRED_PYTHON"
        }
    fi
fi

# Check for virtual environment
VENV_PATHS=(".venv" "venv" "env" ".env")
VENV_FOUND=false

for venv in "${VENV_PATHS[@]}"; do
    if [ -d "$PROJECT_ROOT/$venv" ] && [ -f "$PROJECT_ROOT/$venv/bin/activate" ]; then
        echo "Found virtual environment: $venv"
        source "$PROJECT_ROOT/$venv/bin/activate"
        VENV_FOUND=true
        break
    fi
done

# ALWAYS create .venv if it doesn't exist
if [ ! -d "$PROJECT_ROOT/.venv" ]; then
    echo "[WARN]  No .venv found - Creating it now!"
    VENV_FOUND=false
fi

# If no venv found but .python-version exists, try to create one
if [ "$VENV_FOUND" = false ] && [ -f ".python-version" ]; then
    echo "[PKG] Creating virtual environment..."
    
    PYTHON_CMD=$(find_python "$REQUIRED_PYTHON")
    if [ -n "$PYTHON_CMD" ]; then
        # Try uv first (fastest)
        if command -v uv > /dev/null 2>&1; then
            echo "   Using uv to create .venv"
            uv venv .venv --python "$PYTHON_CMD"
        else
            echo "   Using venv module to create .venv"
            "$PYTHON_CMD" -m venv .venv
        fi
        
        if [ -f ".venv/bin/activate" ]; then
            source .venv/bin/activate
            echo "[PASS] Created and activated virtual environment"
            
            # Install dependencies if pyproject.toml exists
            if [ -f "pyproject.toml" ]; then
                echo "[PKG] Installing project dependencies..."
                if command -v uv > /dev/null 2>&1; then
                    uv pip install -e ".[dev]"
                else
                    pip install -e ".[dev]"
                fi
            fi
        fi
    fi
fi

# Check for uv (fast Python package manager)
if command -v uv > /dev/null 2>&1; then
    echo "uv is available for fast package management"
    export UV_LINK_MODE=copy  # Prevent hardlink issues in CI
else
    # Try to install uv
    if command -v curl > /dev/null 2>&1; then
        echo "[PKG] Installing uv for faster builds..."
        curl -LsSf https://astral.sh/uv/install.sh | sh 2>/dev/null || true
        if [ -d "$HOME/.cargo/bin" ]; then
            export PATH="$HOME/.cargo/bin:$PATH"
        fi
    fi
fi

# Check for Node.js (needed for semantic-release)
if ! command -v node > /dev/null 2>&1; then
    echo "[WARN]  Node.js not found (needed for semantic-release)"
    
    # Check for nvm
    if [ -f "$HOME/.nvm/nvm.sh" ]; then
        source "$HOME/.nvm/nvm.sh"
        nvm use stable 2>/dev/null || nvm install stable
    else
        echo "   Install Node.js 20+ or use nvm"
    fi
else
    NODE_VERSION=$(node --version | grep -oP '\d+' | head -1)
    echo "[PKG] Node.js version: $(node --version)"
fi

# Check for other required tools
echo ""
echo "[SEARCH] Checking required tools:"
command -v git > /dev/null && echo "   [PASS] git: $(git --version | head -1)" || echo "   [FAIL] git: not found"
command -v python > /dev/null && echo "   [PASS] python: $(python --version 2>&1)" || echo "   [FAIL] python: not found"
command -v pip > /dev/null && echo "   [PASS] pip: $(pip --version | cut -d' ' -f1,2)" || echo "   [FAIL] pip: not found"
command -v node > /dev/null && echo "   [PASS] node: $(node --version)" || echo "   [FAIL] node: not found"
command -v npm > /dev/null && echo "   [PASS] npm: $(npm --version)" || echo "   [FAIL] npm: not found"
command -v uv > /dev/null && echo "   [PASS] uv: installed" || echo "   [WARN]  uv: not found (optional, speeds up builds)"

# Set environment variables
export PYTHONPATH="$PROJECT_ROOT/src:$PYTHONPATH"
export PATH="$PROJECT_ROOT/.venv/bin:$HOME/.cargo/bin:$PATH"
export TMPDIR="$PROJECT_ROOT/.tmp"
export TEMP="$PROJECT_ROOT/.tmp"
export TMP="$PROJECT_ROOT/.tmp"
mkdir -p "$TMPDIR"

# Enable colors in output
export FORCE_COLOR=1
export PY_COLORS=1
export TERM=xterm-256color

echo ""
echo "[PASS] Environment setup complete!"
echo "   Python: $(which python)"
echo "   Working directory: $(pwd)"
echo "   Temp directory: $TMPDIR"