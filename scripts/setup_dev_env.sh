#!/bin/bash
# LogReducer Development Environment Setup Script
# This script checks for required tools and sets up the development environment

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}🚀 LogReducer Development Environment Setup${NC}"
echo "=================================================="

# Step 1: Check for required tools
echo -e "\n${BLUE}Step 1: Checking required development tools...${NC}"
if python3 "$SCRIPT_DIR/check_dev_tools.py"; then
    echo -e "${GREEN}✅ All required tools are available!${NC}"
else
    echo -e "${RED}❌ Some required tools are missing.${NC}"
    echo -e "${YELLOW}💡 Run this for installation guidance:${NC}"
    echo "   python scripts/check_dev_tools.py --install"
    echo ""
    echo -e "${YELLOW}💡 Or use a pre-configured VM:${NC}"
    echo "   python scripts/check_dev_tools.py --vm-info"
    exit 1
fi

# Step 2: Setup Python environment
echo -e "\n${BLUE}Step 2: Setting up Python virtual environment...${NC}"
cd "$PROJECT_ROOT"

if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    uv venv .venv
    echo -e "${GREEN}✅ Virtual environment created${NC}"
else
    echo -e "${YELLOW}⚠️  Virtual environment already exists${NC}"
fi

# Step 3: Install dependencies
echo -e "\n${BLUE}Step 3: Installing Python dependencies...${NC}"
uv pip install -e ".[dev,enhanced]"
echo -e "${GREEN}✅ Dependencies installed${NC}"

# Step 4: Initialize Git LFS
echo -e "\n${BLUE}Step 4: Initializing Git LFS...${NC}"
if command -v git-lfs > /dev/null; then
    git lfs install
    echo -e "${GREEN}✅ Git LFS initialized${NC}"
else
    echo -e "${YELLOW}⚠️  Git LFS not available, skipping${NC}"
fi

# Step 5: Install commit hooks
echo -e "\n${BLUE}Step 5: Installing commit hooks...${NC}"
if [ -f "package.json" ]; then
    npm install
    npx husky install
    echo -e "${GREEN}✅ Commit hooks installed${NC}"
else
    echo -e "${YELLOW}⚠️  package.json not found, skipping Husky setup${NC}"
fi

# Step 6: Run verification tests
echo -e "\n${BLUE}Step 6: Running verification tests...${NC}"
if source .venv/bin/activate && python -c "import logreducer; print('Version:', logreducer.__version__)"; then
    echo -e "${GREEN}✅ API import test passed${NC}"
else
    echo -e "${RED}❌ API import test failed${NC}"
    exit 1
fi

# Final summary
echo -e "\n${GREEN}🎉 Development environment setup complete!${NC}"
echo "=================================================="
echo -e "${BLUE}Next steps:${NC}"
echo "1. Activate the virtual environment:"
echo "   source .venv/bin/activate"
echo ""
echo "2. Run tests to verify everything works:"
echo "   pytest tests/ -v"
echo ""
echo "3. Start developing:"
echo "   code .  # Open in VS Code"
echo ""
echo "4. Before committing, verify code quality:"
echo "   black src/ tests/"
echo "   pytest tests/"
echo ""
echo -e "${GREEN}Happy coding! 🚀${NC}"