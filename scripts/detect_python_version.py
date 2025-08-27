#!/usr/bin/env python3
"""
Simplified Python version management using .python-version file.

This script uses a single .python-version file (standard pyenv format) as the
source of truth for Python minimum version requirements. Environment variables
can override this setting.
"""

import sys
import subprocess
import json
import re
import os
import tempfile
from pathlib import Path
from typing import Tuple, Dict, List, Optional


class PythonVersionManager:
    """Manage Python minimum version using .python-version file."""
    
    DEFAULT_VERSION = "3.11"  # Default fallback if nothing is set anywhere
    
    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path(__file__).parent.parent
        self.tmp_dir = self.project_root / '.tmp'
        self.tmp_dir.mkdir(exist_ok=True)
        
        # Set temp directory for all operations
        os.environ['TMPDIR'] = str(self.tmp_dir)
        os.environ['TEMP'] = str(self.tmp_dir)
        os.environ['TMP'] = str(self.tmp_dir)
        
        self.python_version_file = self.project_root / '.python-version'
        
    def get_minimum_version(self) -> str:
        """Get minimum Python version from .python-version file or environment."""
        # 1. Check environment override first
        env_version = os.getenv('PYTHON_MIN_VERSION')
        if env_version:
            print(f"Using Python version from PYTHON_MIN_VERSION environment: {env_version}")
            return env_version
        
        # 2. Check .python-version file
        if self.python_version_file.exists():
            version = self.python_version_file.read_text().strip()
            print(f"Using Python version from .python-version file: {version}")
            return version
        
        # 3. Fall back to default
        print(f"No version file found, using default: {self.DEFAULT_VERSION}")
        return self.DEFAULT_VERSION
    
    def detect_required_version(self) -> Optional[str]:
        """Use Vermin to detect actual required Python version from code."""
        print("Running Vermin to detect required Python version from code...")
        
        try:
            # Run vermin on source code
            result = subprocess.run([
                'vermin', 
                '--target=3',  # Target Python 3 only
                '--no-tips',
                'src/logreducer/'
            ], capture_output=True, text=True, cwd=self.project_root)
            
            # Vermin may output to stderr even on success
            output = result.stdout + result.stderr
            
            if result.returncode != 0 and not output.strip():
                print(f"Warning: Vermin analysis failed with no output")
                return None
            
            # Parse Vermin output for minimum version
            # Look for lines like "Minimum required versions: 3.8" or just "3.8"
            version_match = re.search(r'Minimum required versions?:\s*(\d+\.\d+)', output)
            if not version_match:
                # Look for direct version mentions like "3.8" or "!3.8" 
                version_match = re.search(r'(\d+\.\d+)', output)
            
            if version_match:
                detected = version_match.group(1)
                print(f"Vermin detected minimum required version: {detected}")
                return detected
            else:
                print("Could not parse Vermin output for version requirement")
                return None
                
        except Exception as e:
            print(f"Error running Vermin: {e}")
            return None
    
    def update_minimum_version(self, new_version: str, reason: str = "dependency check"):
        """Update .python-version file with new minimum version."""
        current = self.get_minimum_version()
        
        if self._version_compare(new_version, current) > 0:
            print(f"UPDATING .python-version: {current} -> {new_version} (reason: {reason})")
            self.python_version_file.write_text(new_version + '\n')
            return True
        else:
            print(f"No update needed: current {current} >= detected {new_version}")
            return False
    
    def _version_compare(self, version1: str, version2: str) -> int:
        """Compare two version strings. Returns 1 if v1 > v2, -1 if v1 < v2, 0 if equal."""
        try:
            v1_parts = [int(x) for x in version1.split('.')]
            v2_parts = [int(x) for x in version2.split('.')]
            
            # Pad with zeros for comparison
            max_len = max(len(v1_parts), len(v2_parts))
            v1_parts.extend([0] * (max_len - len(v1_parts)))
            v2_parts.extend([0] * (max_len - len(v2_parts)))
            
            if v1_parts > v2_parts:
                return 1
            elif v1_parts < v2_parts:
                return -1
            else:
                return 0
        except ValueError:
            # If parsing fails, treat as equal
            return 0
    
    def sync_all_configurations(self):
        """Update all configuration files with current minimum version."""
        current_version = self.get_minimum_version()
        print(f"Syncing all configuration files to Python {current_version}")
        
        # Update pyproject.toml
        self._update_pyproject_toml(current_version)
        
        # Update GitHub workflows
        self._update_github_workflows(current_version)
        
        # Update Read the Docs config
        self._update_readthedocs(current_version)
        
        print("All configuration files updated successfully")
    
    def _update_pyproject_toml(self, version: str):
        """Update pyproject.toml with new Python version."""
        pyproject_path = self.project_root / 'pyproject.toml'
        if not pyproject_path.exists():
            return
        
        content = pyproject_path.read_text()
        
        # Update requires-python
        content = re.sub(
            r'requires-python\s*=\s*">=[\d.]+["\']', 
            f'requires-python = ">={version}"',
            content
        )
        
        # Update Python version classifiers
        # Match patterns like "Programming Language :: Python :: 3.11"
        content = re.sub(
            r'"Programming Language :: Python :: \d+\.\d+"', 
            f'"Programming Language :: Python :: {version}"',
            content
        )
        
        # Also update the generic Python 3 classifier if it exists
        if '"Programming Language :: Python :: 3 :: Only"' not in content:
            content = re.sub(
                r'"Programming Language :: Python :: 3"',
                f'"Programming Language :: Python :: 3",\n    "Programming Language :: Python :: {version}",\n    "Programming Language :: Python :: 3 :: Only"',
                content
            )
        
        pyproject_path.write_text(content)
        print(f"Updated pyproject.toml to Python {version}")
    
    def _update_github_workflows(self, version: str):
        """Update all GitHub workflow files with new Python version."""
        workflows_dir = self.project_root / '.github/workflows'
        if not workflows_dir.exists():
            return
        
        for workflow_file in workflows_dir.glob('*.yml'):
            content = workflow_file.read_text()
            updated = False
            
            # Update python-version fields
            if re.search(r'python-version:', content):
                content = re.sub(
                    r"python-version:\s*['\"]?[\d.]+['\"]?",
                    f'python-version: "{version}"',
                    content
                )
                updated = True
            
            # Update environment variables
            if 'PYTHON_VERSION:' in content:
                content = re.sub(
                    r'PYTHON_VERSION:\s*["\']?[\d.]+["\']?',
                    f'PYTHON_VERSION: "{version}"',
                    content
                )
                updated = True
            
            # Update Docker FROM lines to use variables
            content = re.sub(
                r'FROM python:[\d.]+-slim',
                'FROM python:${PYTHON_VERSION}-slim',
                content
            )
            
            if updated:
                workflow_file.write_text(content)
                print(f"Updated {workflow_file.name} to Python {version}")
    
    def _update_readthedocs(self, version: str):
        """Update .readthedocs.yaml with new Python version."""
        rtd_path = self.project_root / '.readthedocs.yaml'
        if not rtd_path.exists():
            return
        
        content = rtd_path.read_text()
        
        # Update python.version
        content = re.sub(
            r'version:\s*["\']*[\d.]+["\']*',
            f'version: "{version}"',
            content
        )
        
        rtd_path.write_text(content)
        print(f"Updated .readthedocs.yaml to Python {version}")
    
    def check_dependencies_version(self) -> Optional[str]:
        """Check dependency versions to determine minimum Python requirement."""
        print("Checking dependency Python version requirements...")
        
        pyproject_path = self.project_root / 'pyproject.toml'
        if not pyproject_path.exists():
            return None
            
        try:
            import tomllib
        except ImportError:
            # Fallback for Python < 3.11
            try:
                import tomli as tomllib
            except ImportError:
                print("Warning: Cannot parse pyproject.toml (install tomllib/tomli)")
                return None
                
        try:
            with open(pyproject_path, 'rb') as f:
                data = tomllib.load(f)
            
            dependencies = data.get('project', {}).get('dependencies', [])
            optional_deps = data.get('project', {}).get('optional-dependencies', {})
            
            # Collect all dependencies
            all_deps = dependencies[:]
            for dep_group in optional_deps.values():
                all_deps.extend(dep_group)
            
            # Known minimum Python requirements for key packages
            dep_requirements = {
                'numpy>=2.0.0': '3.9',
                'scikit-learn>=1.3.0': '3.8', 
                'psutil>=6.0.0': '3.7',
                'sphinx>=8.0.0': '3.9',
                'black>=24.0.0': '3.8',
                'mypy>=1.8.0': '3.8',
                'pytest>=8.0.0': '3.8',
            }
            
            required_version = '3.7'  # Default minimum
            
            for dep in all_deps:
                dep_clean = dep.split(';')[0].strip()  # Remove environment markers
                for pattern, min_version in dep_requirements.items():
                    if dep_clean.startswith(pattern.split('>=')[0]):
                        if self._version_compare(min_version, required_version) > 0:
                            required_version = min_version
                            print(f"Dependency {dep_clean} requires Python {min_version}+")
                            
            return required_version if required_version != '3.7' else None
            
        except Exception as e:
            print(f"Error checking dependencies: {e}")
            return None
    
    def check_and_update(self):
        """Main workflow: detect requirements and update if needed."""
        print("=" * 60)
        print("Python Version Management")
        print("=" * 60)
        
        current_min = self.get_minimum_version()
        print(f"Current minimum version: {current_min}")
        
        # Check both code analysis and dependency requirements
        code_detected = self.detect_required_version()
        deps_detected = self.check_dependencies_version()
        
        # Use the highest requirement
        highest_requirement = current_min
        update_reason = None
        
        if code_detected and self._version_compare(code_detected, highest_requirement) > 0:
            highest_requirement = code_detected
            update_reason = "Vermin code analysis"
            
        if deps_detected and self._version_compare(deps_detected, highest_requirement) > 0:
            highest_requirement = deps_detected  
            update_reason = "dependency requirements"
            
        if update_reason:
            updated = self.update_minimum_version(highest_requirement, update_reason)
            if updated:
                # Re-sync all configurations after update
                self.sync_all_configurations()
        else:
            # Even if no updates needed, sync existing version to all files
            print("Using current minimum version for synchronization")
            self.sync_all_configurations()
        
        print("=" * 60)
        print(f"Final minimum version: {self.get_minimum_version()}")
        print("=" * 60)


def main():
    """Main entry point."""
    manager = PythonVersionManager()
    
    if len(sys.argv) > 1 and sys.argv[1] == 'sync':
        # Just sync current version to all files
        manager.sync_all_configurations()
    else:
        # Full check and update workflow
        manager.check_and_update()


if __name__ == "__main__":
    main()