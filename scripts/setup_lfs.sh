#!/bin/bash
# Setup Git LFS for the LogReducer repository

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Setting up Git LFS for LogReducer${NC}"
echo "===================================="

# Check if git is available
if ! command -v git &> /dev/null; then
    echo -e "${RED}Error: git is not installed${NC}"
    exit 1
fi

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo -e "${YELLOW}Warning: Not in a git repository${NC}"
    echo "Initializing git repository..."
    git init
fi

# Check if Git LFS is installed
if ! command -v git-lfs &> /dev/null; then
    echo -e "${RED}Error: Git LFS is not installed${NC}"
    echo ""
    echo "Please install Git LFS:"
    echo "  Ubuntu/Debian: sudo apt-get install git-lfs"
    echo "  MacOS: brew install git-lfs"
    echo "  Windows: Download from https://git-lfs.github.com/"
    echo ""
    echo "After installation, run this script again."
    exit 1
fi

# Initialize Git LFS
echo -e "\n${GREEN}Initializing Git LFS...${NC}"
git lfs install

# Track files as specified in .gitattributes
echo -e "\n${GREEN}Tracking files with Git LFS...${NC}"

# The patterns are already in .gitattributes, but we ensure they're tracked
git lfs track "*.log"
git lfs track "data/**/*.log"
git lfs track "data/**/*.txt"
git lfs track "data/**/*.csv"
git lfs track "data/**/*.json"
git lfs track "data/**/*.xml"
git lfs track "*.log.gz"
git lfs track "*.log.bz2"
git lfs track "*.log.xz"
git lfs track "*.log.zip"
git lfs track "tests/data/**/*.log"
git lfs track "tests/fixtures/**/*.log"
git lfs track "output/**/*.log"
git lfs track "*.model"
git lfs track "*.weights"
git lfs track "*.h5"
git lfs track "*.hdf5"

echo -e "\n${GREEN}Git LFS Configuration:${NC}"
git lfs track

# Show current LFS status
echo -e "\n${GREEN}Current LFS files:${NC}"
git lfs ls-files 2>/dev/null || echo "No files currently tracked by LFS"

# Check sample files
echo -e "\n${GREEN}Sample files that will use LFS:${NC}"
find data -type f -name "*.log" -exec ls -lh {} \; 2>/dev/null | head -10 || echo "No sample files found"

echo -e "\n${GREEN}✓ Git LFS setup complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Add files to git: git add ."
echo "2. Commit changes: git commit -m 'Add Git LFS support'"
echo "3. Push to remote: git push"
echo ""
echo "Note: Large files will now be stored in Git LFS automatically."