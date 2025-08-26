#!/bin/bash
# LogReducer Release Script
# This script handles the release process with configurable deployment targets

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
    echo -e "${GREEN}✓ Loaded configuration from .env${NC}"
else
    echo -e "${YELLOW}⚠ No .env file found, using defaults${NC}"
fi

# Set defaults if not defined
ENABLE_PYPI_DEPLOYMENT=${ENABLE_PYPI_DEPLOYMENT:-OFF}
ENABLE_GITHUB_RELEASE=${ENABLE_GITHUB_RELEASE:-OFF}
ENABLE_ARTIFACTORY_DEPLOYMENT=${ENABLE_ARTIFACTORY_DEPLOYMENT:-ON}
ENABLE_SEMANTIC_RELEASE=${ENABLE_SEMANTIC_RELEASE:-ON}
DRY_RUN=${DRY_RUN:-OFF}
RUN_TESTS_BEFORE_RELEASE=${RUN_TESTS_BEFORE_RELEASE:-ON}

# Function to print status
print_status() {
    echo -e "\n${GREEN}==>${NC} $1"
}

print_error() {
    echo -e "\n${RED}ERROR:${NC} $1"
    exit 1
}

print_warning() {
    echo -e "${YELLOW}WARNING:${NC} $1"
}

# Check if we're in the project root
if [ ! -f "pyproject.toml" ]; then
    print_error "Must be run from project root directory"
fi

# Display configuration
echo -e "\n${GREEN}LogReducer Release Configuration${NC}"
echo "=================================="
echo "PyPI Deployment:        $ENABLE_PYPI_DEPLOYMENT"
echo "GitHub Release:         $ENABLE_GITHUB_RELEASE"
echo "Artifactory Deployment: $ENABLE_ARTIFACTORY_DEPLOYMENT"
echo "Semantic Release:       $ENABLE_SEMANTIC_RELEASE"
echo "Dry Run:               $DRY_RUN"
echo "Run Tests:             $RUN_TESTS_BEFORE_RELEASE"
echo ""

# Check for required tools
print_status "Checking required tools..."

command -v python3 >/dev/null 2>&1 || print_error "Python 3 is required"
command -v npm >/dev/null 2>&1 || print_error "npm is required for semantic release"
command -v git >/dev/null 2>&1 || print_error "git is required"

# Check git status
print_status "Checking git status..."
if [ -n "$(git status --porcelain)" ]; then
    print_warning "You have uncommitted changes"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Get current branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "Current branch: $CURRENT_BRANCH"

# Run tests if enabled
if [ "$RUN_TESTS_BEFORE_RELEASE" = "ON" ]; then
    print_status "Running tests..."
    if [ "$DRY_RUN" = "OFF" ]; then
        python3 -m pytest tests/ || print_error "Tests failed"
        echo -e "${GREEN}✓ All tests passed${NC}"
    else
        echo "(Skipped in dry run)"
    fi
fi

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    print_status "Installing npm dependencies..."
    if [ "$DRY_RUN" = "OFF" ]; then
        npm ci
    else
        echo "(Skipped in dry run)"
    fi
fi

# Build Python package
print_status "Building Python package..."
if [ "$DRY_RUN" = "OFF" ]; then
    rm -rf dist/
    python3 -m pip install --quiet build
    python3 -m build
    echo -e "${GREEN}✓ Package built successfully${NC}"
else
    echo "(Skipped in dry run)"
fi

# Run semantic release if enabled
if [ "$ENABLE_SEMANTIC_RELEASE" = "ON" ]; then
    print_status "Running semantic release..."
    
    if [ "$DRY_RUN" = "ON" ]; then
        npm run release:dry-run
    else
        npm run release
        
        # Update VERSION file
        VERSION=$(node -p "require('./package.json').version")
        echo "$VERSION" > VERSION
        echo -e "${GREEN}✓ Version updated to $VERSION${NC}"
    fi
else
    print_warning "Semantic release is disabled"
fi

# Deploy to Artifactory if enabled
if [ "$ENABLE_ARTIFACTORY_DEPLOYMENT" = "ON" ] && [ "$CURRENT_BRANCH" = "main" ]; then
    print_status "Deploying to JFrog Artifactory..."
    
    if [ -z "$ARTIFACTORY_USERNAME" ] || [ -z "$ARTIFACTORY_PASSWORD" ]; then
        print_error "Artifactory credentials not set. Please set ARTIFACTORY_USERNAME and ARTIFACTORY_PASSWORD"
    fi
    
    if [ "$DRY_RUN" = "OFF" ]; then
        python3 -m pip install --quiet twine
        twine upload \
            --repository-url "${ARTIFACTORY_URL:-https://hypersec.jfrog.io/artifactory/api/pypi/hypersec-pypi-local/}" \
            --username "$ARTIFACTORY_USERNAME" \
            --password "$ARTIFACTORY_PASSWORD" \
            --non-interactive \
            --disable-progress-bar \
            dist/*
        echo -e "${GREEN}✓ Deployed to Artifactory${NC}"
    else
        echo "(Skipped in dry run)"
    fi
else
    if [ "$ENABLE_ARTIFACTORY_DEPLOYMENT" = "OFF" ]; then
        print_warning "Artifactory deployment is disabled"
    elif [ "$CURRENT_BRANCH" != "main" ]; then
        print_warning "Artifactory deployment only runs from main branch"
    fi
fi

# Deploy to PyPI if enabled
if [ "$ENABLE_PYPI_DEPLOYMENT" = "ON" ] && [ "$CURRENT_BRANCH" = "main" ]; then
    print_status "Deploying to PyPI..."
    
    if [ -z "$PYPI_API_TOKEN" ]; then
        print_error "PyPI API token not set. Please set PYPI_API_TOKEN"
    fi
    
    if [ "$DRY_RUN" = "OFF" ]; then
        python3 -m pip install --quiet twine
        twine upload \
            --username __token__ \
            --password "$PYPI_API_TOKEN" \
            --non-interactive \
            --disable-progress-bar \
            dist/*
        echo -e "${GREEN}✓ Deployed to PyPI${NC}"
    else
        echo "(Skipped in dry run)"
    fi
else
    if [ "$ENABLE_PYPI_DEPLOYMENT" = "OFF" ]; then
        print_warning "PyPI deployment is disabled"
    elif [ "$CURRENT_BRANCH" != "main" ]; then
        print_warning "PyPI deployment only runs from main branch"
    fi
fi

# Create GitHub release if enabled
if [ "$ENABLE_GITHUB_RELEASE" = "ON" ] && [ "$CURRENT_BRANCH" = "main" ]; then
    print_status "Creating GitHub release..."
    
    if [ "$DRY_RUN" = "OFF" ]; then
        if [ "$ENABLE_SEMANTIC_RELEASE" = "ON" ]; then
            echo "GitHub release handled by semantic-release"
        else
            print_warning "Manual GitHub release creation not implemented"
        fi
    else
        echo "(Skipped in dry run)"
    fi
else
    if [ "$ENABLE_GITHUB_RELEASE" = "OFF" ]; then
        print_warning "GitHub release is disabled"
    elif [ "$CURRENT_BRANCH" != "main" ]; then
        print_warning "GitHub release only created from main branch"
    fi
fi

# Summary
echo -e "\n${GREEN}Release Process Complete!${NC}"
echo "========================="
if [ "$DRY_RUN" = "ON" ]; then
    echo -e "${YELLOW}This was a dry run - no changes were made${NC}"
else
    if [ -f VERSION ]; then
        echo "Released version: $(cat VERSION)"
    fi
fi

echo -e "\nDeployment Summary:"
[ "$ENABLE_ARTIFACTORY_DEPLOYMENT" = "ON" ] && echo "  ✓ Artifactory" || echo "  ✗ Artifactory (disabled)"
[ "$ENABLE_PYPI_DEPLOYMENT" = "ON" ] && echo "  ✓ PyPI" || echo "  ✗ PyPI (disabled)"
[ "$ENABLE_GITHUB_RELEASE" = "ON" ] && echo "  ✓ GitHub Release" || echo "  ✗ GitHub Release (disabled)"

echo -e "\n${GREEN}Done!${NC}"