#!/usr/bin/env python3
"""
Package build script for LogReducer
"""

import subprocess
import sys
import os
import shutil
from pathlib import Path


def run_command(cmd, description):
    """Run a command and handle errors"""
    print(f"🔄 {description}")
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed")
        if result.stdout:
            print(f"   Output: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed")
        print(f"   Error: {e.stderr.strip() if e.stderr else str(e)}")
        return False


def clean_build_artifacts():
    """Clean previous build artifacts"""
    print("🧹 Cleaning build artifacts")
    
    dirs_to_clean = ['build', 'dist', '*.egg-info']
    for dir_pattern in dirs_to_clean:
        if '*' in dir_pattern:
            import glob
            for path in glob.glob(dir_pattern):
                if os.path.isdir(path):
                    shutil.rmtree(path)
                    print(f"   Removed: {path}")
        else:
            if os.path.exists(dir_pattern):
                shutil.rmtree(dir_pattern)
                print(f"   Removed: {dir_pattern}")
    
    print("✅ Build artifacts cleaned")


def check_dependencies():
    """Check that required dependencies are installed"""
    print("🔍 Checking build dependencies")
    
    required_packages = ['build', 'twine']
    missing = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"   ✅ {package} is installed")
        except ImportError:
            missing.append(package)
            print(f"   ❌ {package} is missing")
    
    if missing:
        print(f"Installing missing packages: {', '.join(missing)}")
        cmd = f"{sys.executable} -m pip install {' '.join(missing)}"
        if not run_command(cmd, f"Installing {', '.join(missing)}"):
            return False
    
    return True


def build_package():
    """Build the package"""
    print("📦 Building package")
    
    # Ensure we're in the right directory
    os.chdir(Path(__file__).parent.parent)
    
    # Build the package
    cmd = f"{sys.executable} -m build"
    if not run_command(cmd, "Building package with python -m build"):
        return False
    
    # List built artifacts
    if os.path.exists('dist'):
        print("📋 Built artifacts:")
        for item in os.listdir('dist'):
            file_path = os.path.join('dist', item)
            size = os.path.getsize(file_path) / 1024  # KB
            print(f"   - {item} ({size:.1f} KB)")
    
    return True


def validate_package():
    """Validate the built package"""
    print("🔍 Validating package")
    
    if not os.path.exists('dist'):
        print("❌ No dist directory found")
        return False
    
    # Check with twine
    cmd = f"{sys.executable} -m twine check dist/*"
    if not run_command(cmd, "Validating package with twine"):
        return False
    
    return True


def main():
    """Main build process"""
    print("🚀 LogReducer Package Build Script")
    print("=" * 50)
    
    steps = [
        ("Checking dependencies", check_dependencies),
        ("Cleaning build artifacts", clean_build_artifacts), 
        ("Building package", build_package),
        ("Validating package", validate_package),
    ]
    
    failed_steps = []
    
    for step_name, step_func in steps:
        print(f"\n📋 Step: {step_name}")
        try:
            if not step_func():
                failed_steps.append(step_name)
        except Exception as e:
            print(f"❌ Step failed with exception: {e}")
            failed_steps.append(step_name)
    
    print("\n" + "=" * 50)
    print("📊 Build Summary")
    print("=" * 50)
    
    if failed_steps:
        print("❌ Build failed!")
        print("Failed steps:")
        for step in failed_steps:
            print(f"   - {step}")
        sys.exit(1)
    else:
        print("✅ Build completed successfully!")
        print("Package ready for deployment")
        
        if os.path.exists('dist'):
            print(f"📦 Artifacts in dist/:")
            for item in sorted(os.listdir('dist')):
                print(f"   - {item}")


if __name__ == "__main__":
    main()