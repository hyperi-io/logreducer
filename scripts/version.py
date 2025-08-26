#!/usr/bin/env python3
"""
Version update script for semantic-release
"""

import sys
import re
import os
from pathlib import Path


def update_init_py(version):
    """Update version in __init__.py"""
    init_file = Path("logreducer/__init__.py")
    
    if not init_file.exists():
        print(f"❌ {init_file} not found")
        return False
    
    # Read current content
    with open(init_file, 'r') as f:
        content = f.read()
    
    # Update version
    new_content = re.sub(
        r'__version__\s*=\s*["\'][^"\']*["\']',
        f'__version__ = "{version}"',
        content
    )
    
    # Write back
    with open(init_file, 'w') as f:
        f.write(new_content)
    
    print(f"✅ Updated {init_file} to version {version}")
    return True


def update_pyproject_toml(version):
    """Update version in pyproject.toml"""
    pyproject_file = Path("pyproject.toml")
    
    if not pyproject_file.exists():
        print(f"❌ {pyproject_file} not found")
        return False
    
    # Read current content
    with open(pyproject_file, 'r') as f:
        content = f.read()
    
    # Update version in [project] section
    new_content = re.sub(
        r'version\s*=\s*["\'][^"\']*["\']',
        f'version = "{version}"',
        content
    )
    
    # Write back
    with open(pyproject_file, 'w') as f:
        f.write(new_content)
    
    print(f"✅ Updated {pyproject_file} to version {version}")
    return True


def update_package_json(version):
    """Update version in package.json"""
    package_file = Path("package.json")
    
    if not package_file.exists():
        print(f"❌ {package_file} not found")
        return False
    
    # Read current content
    with open(package_file, 'r') as f:
        content = f.read()
    
    # Update version
    new_content = re.sub(
        r'"version"\s*:\s*"[^"]*"',
        f'"version": "{version}"',
        content
    )
    
    # Write back
    with open(package_file, 'w') as f:
        f.write(new_content)
    
    print(f"✅ Updated {package_file} to version {version}")
    return True


def main():
    """Main version update process"""
    if len(sys.argv) != 2:
        print("Usage: python update_version.py <version>")
        print("Example: python update_version.py 1.2.3")
        sys.exit(1)
    
    version = sys.argv[1]
    
    # Validate version format (basic semver check)
    if not re.match(r'^\d+\.\d+\.\d+(-.*)?$', version):
        print(f"❌ Invalid version format: {version}")
        print("Expected format: X.Y.Z or X.Y.Z-suffix")
        sys.exit(1)
    
    print(f"🔄 Updating version to {version}")
    
    # Change to project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    os.chdir(project_root)
    
    updates = [
        ("logreducer/__init__.py", update_init_py),
        ("pyproject.toml", update_pyproject_toml), 
        ("package.json", update_package_json),
    ]
    
    failed_updates = []
    
    for file_name, update_func in updates:
        try:
            if not update_func(version):
                failed_updates.append(file_name)
        except Exception as e:
            print(f"❌ Error updating {file_name}: {e}")
            failed_updates.append(file_name)
    
    if failed_updates:
        print(f"\n❌ Failed to update: {', '.join(failed_updates)}")
        sys.exit(1)
    else:
        print(f"\n✅ Successfully updated all files to version {version}")


if __name__ == "__main__":
    main()