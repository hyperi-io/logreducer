#!/bin/bash
# Deploy to JFrog Artifactory - Manual Testing Script
set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== JFrog Artifactory Deployment Test ===${NC}"
echo ""

# Check for required environment variables
if [ -z "${ARTIFACTORY_USERNAME:-}" ] || [ -z "${ARTIFACTORY_PASSWORD:-}" ]; then
    echo -e "${RED}ERROR: Missing credentials${NC}"
    echo ""
    echo "Please set environment variables:"
    echo "  export ARTIFACTORY_USERNAME=your-username"
    echo "  export ARTIFACTORY_PASSWORD=your-password-or-token"
    echo ""
    echo "Or create a .env file with:"
    echo "  ARTIFACTORY_USERNAME=your-username"
    echo "  ARTIFACTORY_PASSWORD=your-password-or-token"
    exit 1
fi

# Load .env if it exists
if [ -f .env ]; then
    echo -e "${BLUE}Loading .env file...${NC}"
    export $(cat .env | grep -v '^#' | xargs)
fi

# JFrog Artifactory configuration
ARTIFACTORY_URL="${ARTIFACTORY_URL:-https://hypersec.jfrog.io/artifactory/api/pypi/hypersec-pypi-local/}"
echo -e "${BLUE}Repository URL: $ARTIFACTORY_URL${NC}"

# Check if packages exist
if [ ! -d "dist" ] || [ -z "$(ls -A dist/*.whl 2>/dev/null)" ]; then
    echo -e "${YELLOW}No packages found. Building...${NC}"
    source .venv/bin/activate
    python -m build
fi

echo -e "${BLUE}Packages to upload:${NC}"
ls -la dist/*.whl dist/*.tar.gz

# Test authentication first
echo -e "${BLUE}Testing authentication...${NC}"
curl -u "${ARTIFACTORY_USERNAME}:${ARTIFACTORY_PASSWORD}" \
     "${ARTIFACTORY_URL%/api/pypi/*}/api/system/ping" \
     -f -s -o /dev/null \
     && echo -e "${GREEN}✓ Authentication successful${NC}" \
     || { echo -e "${RED}✗ Authentication failed${NC}"; exit 1; }

# Install twine if needed
if ! command -v twine &> /dev/null; then
    echo -e "${BLUE}Installing twine...${NC}"
    pip install --upgrade twine
fi

# Configure twine
export TWINE_USERNAME="${ARTIFACTORY_USERNAME}"
export TWINE_PASSWORD="${ARTIFACTORY_PASSWORD}"
export TWINE_REPOSITORY_URL="${ARTIFACTORY_URL}"

echo ""
echo -e "${YELLOW}Ready to upload to JFrog Artifactory${NC}"
echo -e "${YELLOW}Repository: $ARTIFACTORY_URL${NC}"
echo ""
read -p "Continue with upload? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${BLUE}Uploading packages...${NC}"
    
    # Upload with twine
    twine upload \
        --repository-url "$ARTIFACTORY_URL" \
        --verbose \
        dist/*
    
    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}=== SUCCESS ===${NC}"
        echo -e "${GREEN}Packages uploaded to JFrog Artifactory!${NC}"
        echo ""
        echo "View in JFrog UI:"
        echo "  ${ARTIFACTORY_URL%/api/pypi/*}"
        echo ""
        echo "Install with pip:"
        echo "  pip install logreducer --index-url $ARTIFACTORY_URL"
    else
        echo -e "${RED}Upload failed!${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}Upload cancelled${NC}"
fi