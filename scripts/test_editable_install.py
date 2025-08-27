#!/usr/bin/env python3
"""
Test script to verify PEP 660 compliant editable installs
This ensures compatibility with pip 25.0+ which removes legacy editable support
"""

import sys
import subprocess
import tempfile
from pathlib import Path
import venv
import os


def test_editable_install():
    """Test that editable installs work with modern pip and setuptools"""
    
    print("Testing PEP 660 compliant editable install...")
    
    # Get project root and use .tmp directory
    project_root = Path(__file__).parent.parent
    tmp_dir = project_root / ".tmp"
    tmp_dir.mkdir(exist_ok=True)
    
    # Create a temporary virtual environment in project .tmp
    with tempfile.TemporaryDirectory(dir=tmp_dir) as temp_dir:
        venv_dir = Path(temp_dir) / "test_venv"
        
        # Create virtual environment
        print(f"Creating test environment in {venv_dir}")
        venv.create(venv_dir, with_pip=True)
        
        # Get paths
        if sys.platform == "win32":
            python_exe = venv_dir / "Scripts" / "python.exe"
            pip_exe = venv_dir / "Scripts" / "pip.exe"
        else:
            python_exe = venv_dir / "bin" / "python"
            pip_exe = venv_dir / "bin" / "pip"
        
        try:
            # Upgrade pip and setuptools to latest
            print("Upgrading pip and setuptools...")
            subprocess.run([
                str(pip_exe), "install", "--upgrade", 
                "pip>=22.1", "setuptools>=64.0.0", "wheel"
            ], check=True, capture_output=True, text=True)
            
            # Test editable install
            print("Testing editable install...")
            result = subprocess.run([
                str(pip_exe), "install", "-e", "."
            ], check=True, capture_output=True, text=True)
            
            # Test that import works
            print("Testing import...")
            result = subprocess.run([
                str(python_exe), "-c", "import logreducer; print('✅ Import successful')"
            ], check=True, capture_output=True, text=True)
            
            print("✅ PEP 660 compliant editable install works correctly!")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Test failed: {e}")
            if e.stdout:
                print(f"STDOUT: {e.stdout}")
            if e.stderr:
                print(f"STDERR: {e.stderr}")
            return False


if __name__ == "__main__":
    success = test_editable_install()
    sys.exit(0 if success else 1)