#!/bin/bash
# Python Version Detection and Update Script
# This script runs the Python version detection and updates all configuration files

set -euo pipefail

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load environment configuration
if [[ -f "$PROJECT_ROOT/.env" ]]; then
    source "$PROJECT_ROOT/.env"
fi

# Get entity name for branding
ENTITY_NAME="${CICD_ENTITY:-HyperSec}"

echo "=================================================="
echo "${ENTITY_NAME} Python Version Detection & Update"
echo "=================================================="
echo

# Ensure we have the required dependencies
echo "INSTALLING: Required dependencies..."
python -m pip install --upgrade vermin python-dotenv pyyaml

# Run the detection script
echo "RUNNING: Python version detection..."
python "$SCRIPT_DIR/detect_python_version.py" "$@"

echo
echo "SUCCESS: Python version detection and update complete!"
echo "   Review the changes and commit them to apply across your project."