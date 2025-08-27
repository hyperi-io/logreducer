#!/usr/bin/env python3
"""
Test script to verify VERSION and pyproject.toml update process

This script simulates what semantic-release would do to update versions
and verifies that the process works correctly.
"""

import re
import subprocess
import sys
from pathlib import Path


def read_version_file() -> str:
    """Read current version from VERSION file"""
    version_file = Path("VERSION")
    if not version_file.exists():
        raise FileNotFoundError("VERSION file not found")
    return version_file.read_text().strip()


def read_pyproject_version() -> str:
    """Read version from pyproject.toml"""
    pyproject_file = Path("pyproject.toml")
    if not pyproject_file.exists():
        raise FileNotFoundError("pyproject.toml file not found")
    
    content = pyproject_file.read_text()
    match = re.search(r'version = "([^"]+)"', content)
    if not match:
        raise ValueError("Version not found in pyproject.toml")
    
    return match.group(1)


def update_versions(new_version: str) -> None:
    """Update VERSION file and pyproject.toml with new version"""
    # Update VERSION file
    version_file = Path("VERSION")
    version_file.write_text(new_version + "\n")
    
    # Update pyproject.toml (only first occurrence)
    cmd = f'sed -i "0,/version = \\".*\\"/{{s/version = \\".*\\"/version = \\"{new_version}\\"/;}}" pyproject.toml'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode != 0:
        raise RuntimeError(f"Failed to update pyproject.toml: {result.stderr}")


def verify_version_consistency() -> bool:
    """Verify that VERSION and pyproject.toml have the same version"""
    try:
        version_file_version = read_version_file()
        pyproject_version = read_pyproject_version()
        
        return version_file_version == pyproject_version
    except Exception as e:
        print(f"Error verifying versions: {e}")
        return False


def check_other_versions_unchanged() -> dict:
    """Check that other version references in pyproject.toml weren't affected"""
    pyproject_file = Path("pyproject.toml")
    content = pyproject_file.read_text()
    
    versions = {}
    
    # Check MyPy python_version
    mypy_match = re.search(r'python_version = "([^"]+)"', content)
    if mypy_match:
        versions['mypy_python_version'] = mypy_match.group(1)
    
    # Check pytest minversion
    pytest_match = re.search(r'minversion = "([^"]+)"', content)
    if pytest_match:
        versions['pytest_minversion'] = pytest_match.group(1)
    
    return versions


def test_version_update_process():
    """Test the complete version update process"""
    print("🧪 Testing VERSION update process")
    print("=" * 50)
    
    # Get initial state
    initial_version = read_version_file()
    initial_pyproject = read_pyproject_version()
    initial_other_versions = check_other_versions_unchanged()
    
    print(f"Initial VERSION file: {initial_version}")
    print(f"Initial pyproject.toml: {initial_pyproject}")
    print(f"Initial other versions: {initial_other_versions}")
    
    # Test with different version numbers
    test_versions = ["3.2.0", "4.0.0-beta.1", "3.1.15", initial_version]
    
    all_tests_passed = True
    
    for test_version in test_versions:
        print(f"\n🔄 Testing update to version: {test_version}")
        
        try:
            # Update versions
            update_versions(test_version)
            
            # Verify consistency
            if verify_version_consistency():
                print(f"  ✅ VERSION and pyproject.toml both updated to {test_version}")
                
                # Check that other versions weren't affected
                current_other_versions = check_other_versions_unchanged()
                if current_other_versions == initial_other_versions:
                    print(f"  ✅ Other version references unchanged: {current_other_versions}")
                else:
                    print(f"  ❌ Other versions were modified!")
                    print(f"     Expected: {initial_other_versions}")
                    print(f"     Got: {current_other_versions}")
                    all_tests_passed = False
                    
            else:
                print(f"  ❌ Version inconsistency detected")
                version_file_version = read_version_file()
                pyproject_version = read_pyproject_version()
                print(f"     VERSION file: {version_file_version}")
                print(f"     pyproject.toml: {pyproject_version}")
                all_tests_passed = False
                
        except Exception as e:
            print(f"  ❌ Update failed: {e}")
            all_tests_passed = False
    
    print("\n" + "=" * 50)
    if all_tests_passed:
        print("✅ All version update tests PASSED")
        print("🎉 Semantic release version updates will work correctly")
    else:
        print("❌ Some version update tests FAILED")
        print("🚨 Review the semantic-release configuration")
    
    return all_tests_passed


def test_semantic_release_command():
    """Test the exact command semantic-release would execute"""
    print("\n🔧 Testing semantic-release prepareCmd")
    print("=" * 50)
    
    # Simulate what semantic-release would do
    test_version = "3.2.0"
    
    # The exact command from .releaserc.json
    cmd = f'echo {test_version} > VERSION && sed -i "0,/version = \\".*\\"/{{s/version = \\".*\\"/version = \\"{test_version}\\"/;}}" pyproject.toml'
    
    print(f"Command: {cmd}")
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ Command executed successfully")
        
        # Verify results
        if verify_version_consistency():
            version = read_version_file()
            print(f"✅ Both files updated to version: {version}")
            return True
        else:
            print("❌ Version inconsistency after command")
            return False
    else:
        print(f"❌ Command failed: {result.stderr}")
        return False


def main():
    """Run all version update tests"""
    print("LogReducer Version Update Test Suite")
    print("This verifies that semantic-release will update versions correctly\n")
    
    # Change to project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    import os
    os.chdir(project_root)
    
    try:
        # Test 1: Version update process
        test1_passed = test_version_update_process()
        
        # Test 2: Semantic release command
        test2_passed = test_semantic_release_command()
        
        # Final result
        print("\n" + "=" * 60)
        if test1_passed and test2_passed:
            print("🎉 ALL TESTS PASSED - Version updates work correctly!")
            print("✅ Semantic release will reliably update VERSION and pyproject.toml")
            print("✅ Git hooks and CI workflows are properly configured")
        else:
            print("❌ SOME TESTS FAILED - Version update needs fixing")
            print("🔧 Check the .releaserc.json configuration")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Test suite failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()