#!/usr/bin/env python3
"""
Enforce Python version consistency across all development tools and environments.
This script ensures that the version in .python-version is used everywhere.
"""

import os
import sys
import subprocess
import json
from pathlib import Path
from typing import Tuple, Optional

class PythonVersionEnforcer:
    """Enforce Python version consistency across the project."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.python_version_file = self.project_root / '.python-version'
        self.venv_path = self.project_root / '.venv'
        
    def get_required_version(self) -> str:
        """Get the required Python version from .python-version file."""
        if not self.python_version_file.exists():
            print("ERROR: .python-version file not found!")
            sys.exit(1)
        
        version = self.python_version_file.read_text().strip()
        print(f"Required Python version: {version}")
        return version
    
    def get_venv_version(self) -> Optional[str]:
        """Get the Python version used by the current .venv."""
        venv_python = self.venv_path / 'bin' / 'python'
        if not venv_python.exists():
            return None
        
        try:
            result = subprocess.run(
                [str(venv_python), '--version'],
                capture_output=True,
                text=True
            )
            # Parse version from output like "Python 3.12.0"
            version = result.stdout.strip().split()[-1]
            major_minor = '.'.join(version.split('.')[:2])
            return major_minor
        except Exception as e:
            print(f"Error checking venv Python version: {e}")
            return None
    
    def enforce_venv(self, required_version: str) -> bool:
        """Ensure .venv uses the required Python version."""
        current_venv_version = self.get_venv_version()
        required_major_minor = '.'.join(required_version.split('.')[:2])
        
        if current_venv_version == required_major_minor:
            print(f"SUCCESS: .venv already uses Python {current_venv_version}")
            return True
        
        if current_venv_version:
            print(f"WARNING: .venv uses Python {current_venv_version}, but {required_major_minor} is required")
            print("Removing old .venv...")
            import shutil
            shutil.rmtree(self.venv_path)
        
        print(f"Creating new .venv with Python {required_version}...")
        
        # Try to find the right Python executable
        python_cmd = self.find_python_executable(required_version)
        if not python_cmd:
            print(f"ERROR: Python {required_version} not found on system!")
            print("\nPlease install the required Python version using one of these methods:")
            print(f"  pyenv install {required_version}")
            print(f"  brew install python@{required_major_minor}  # macOS")
            print(f"  sudo apt install python{required_major_minor}  # Ubuntu/Debian")
            return False
        
        # Create venv with the correct Python version
        if self.create_venv_with_uv(python_cmd):
            print("SUCCESS: Virtual environment created with uv")
        elif self.create_venv_with_python(python_cmd):
            print("SUCCESS: Virtual environment created with venv module")
        else:
            print("ERROR: Failed to create virtual environment")
            return False
        
        return True
    
    def find_python_executable(self, version: str) -> Optional[str]:
        """Find Python executable matching the required version."""
        major_minor = '.'.join(version.split('.')[:2])
        
        # Try different Python command variations
        candidates = [
            f"python{version}",
            f"python{major_minor}",
            "python3",
            "python"
        ]
        
        for cmd in candidates:
            if self.check_python_version(cmd, major_minor):
                return cmd
        
        return None
    
    def check_python_version(self, cmd: str, required_version: str) -> bool:
        """Check if a Python command matches the required version."""
        try:
            result = subprocess.run(
                [cmd, '--version'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                version = result.stdout.strip().split()[-1]
                major_minor = '.'.join(version.split('.')[:2])
                if major_minor == required_version:
                    print(f"Found Python {version} at: {cmd}")
                    return True
        except FileNotFoundError:
            pass
        return False
    
    def create_venv_with_uv(self, python_cmd: str) -> bool:
        """Try to create venv using uv."""
        try:
            result = subprocess.run(
                ['uv', 'venv', '.venv', '--python', python_cmd],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    def create_venv_with_python(self, python_cmd: str) -> bool:
        """Create venv using Python's venv module."""
        try:
            result = subprocess.run(
                [python_cmd, '-m', 'venv', '.venv'],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception as e:
            print(f"Error creating venv: {e}")
            return False
    
    def update_vscode_settings(self, python_version: str):
        """Ensure VS Code settings use the correct Python interpreter."""
        vscode_dir = self.project_root / '.vscode'
        vscode_dir.mkdir(exist_ok=True)
        
        settings_file = vscode_dir / 'settings.json'
        
        # Default Python path for the venv
        python_path = "${workspaceFolder}/.venv/bin/python"
        
        if settings_file.exists():
            # Update existing settings
            try:
                with open(settings_file, 'r') as f:
                    settings = json.load(f)
            except json.JSONDecodeError:
                settings = {}
        else:
            settings = {}
        
        # Update Python interpreter path
        settings['python.defaultInterpreterPath'] = python_path
        
        # Write back settings
        with open(settings_file, 'w') as f:
            json.dump(settings, f, indent=4)
        
        print("Updated VS Code settings to use .venv Python")
    
    def create_activation_hook(self):
        """Create shell hooks to automatically check Python version on activation."""
        activate_script = self.venv_path / 'bin' / 'activate'
        if not activate_script.exists():
            return
        
        # Add version check to activation script
        hook_marker = "# PYTHON_VERSION_CHECK"
        hook_code = f"""
{hook_marker}
# Enforce Python version from .python-version
if [ -f "{self.python_version_file}" ]; then
    REQUIRED_VERSION=$(cat {self.python_version_file} | tr -d '[:space:]')
    CURRENT_VERSION=$(python --version 2>&1 | grep -oP '\\d+\\.\\d+' || true)
    REQUIRED_MAJOR_MINOR=$(echo "$REQUIRED_VERSION" | cut -d. -f1,2)
    
    if [ "$CURRENT_VERSION" != "$REQUIRED_MAJOR_MINOR" ]; then
        echo "WARNING: Python version mismatch!"
        echo "  Required: $REQUIRED_VERSION (from .python-version)"
        echo "  Current:  $CURRENT_VERSION"
        echo ""
        echo "Run: ./scripts/setup_venv.sh to fix this"
    fi
fi
"""
        
        # Check if hook already exists
        with open(activate_script, 'r') as f:
            content = f.read()
        
        if hook_marker not in content:
            # Add hook at the end of the file
            with open(activate_script, 'a') as f:
                f.write(hook_code)
            print("Added Python version check to venv activation script")
    
    def check_pyenv_local(self):
        """Check if pyenv is being used and set local version."""
        pyenv_version_file = self.project_root / '.python-version'
        
        # Check if pyenv is installed
        try:
            result = subprocess.run(['pyenv', '--version'], capture_output=True)
            if result.returncode == 0:
                # pyenv is installed, set local version
                required_version = self.get_required_version()
                subprocess.run(['pyenv', 'local', required_version], cwd=self.project_root)
                print(f"Set pyenv local version to {required_version}")
        except FileNotFoundError:
            # pyenv not installed, skip
            pass
    
    def run_enforcement(self):
        """Run all enforcement checks."""
        print("=" * 60)
        print("Python Version Enforcement")
        print("=" * 60)
        
        # Get required version
        required_version = self.get_required_version()
        
        # Enforce venv version
        if not self.enforce_venv(required_version):
            print("\nERROR: Failed to enforce Python version in .venv")
            sys.exit(1)
        
        # Update VS Code settings
        self.update_vscode_settings(required_version)
        
        # Create activation hook
        self.create_activation_hook()
        
        # Check pyenv if available
        self.check_pyenv_local()
        
        print("\n" + "=" * 60)
        print("SUCCESS: Python version enforcement complete!")
        print("=" * 60)
        print(f"\nAll tools are now configured to use Python {required_version}")
        print("\nNext steps:")
        print("  1. Activate the virtual environment:")
        print("     source .venv/bin/activate")
        print("  2. Install dependencies:")
        print("     pip install -e '.[dev,enhanced]'")
        print("  3. Restart VS Code to pick up the new settings")


def main():
    enforcer = PythonVersionEnforcer()
    enforcer.run_enforcement()


if __name__ == "__main__":
    main()