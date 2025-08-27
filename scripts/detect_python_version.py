#!/usr/bin/env python3
"""
Dynamic Python minimum version detection script using Vermin.

This script uses a centralized configuration system with environment overrides
to detect and manage Python minimum version requirements. It only increases
versions (never decreases) based on actual code analysis.
"""

import sys
import subprocess
import json
import re
import os
import yaml
import tempfile
from pathlib import Path
from typing import Tuple, Dict, List, Optional
from dotenv import load_dotenv


class PythonVersionDetector:
    """Detect and manage Python minimum version requirements using Vermin."""
    
    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path(__file__).parent.parent
        self.tmp_dir = self.project_root / '.tmp'
        self.tmp_dir.mkdir(exist_ok=True)
        
        # Set temp directory for all operations
        os.environ['TMPDIR'] = str(self.tmp_dir)
        os.environ['TEMP'] = str(self.tmp_dir)
        os.environ['TMP'] = str(self.tmp_dir)
        
        self.load_configuration()
        
        # Configuration files to update
        self.config_files = {
            'pyproject.toml': self._update_pyproject_toml,
            '.github/workflows/ci.yml': self._update_github_workflow,
            '.readthedocs.yaml': self._update_readthedocs,
            'docs/conf.py': None,  # Read-only reference
        }
        
    def load_configuration(self):
        """Load configuration from YAML file and environment variables."""
        # Load .env file if it exists
        env_path = self.project_root / '.env'
        if env_path.exists():
            load_dotenv(env_path)
        
        # Load YAML configuration
        config_path = self.project_root / '.python-version-config.yaml'
        if config_path.exists():
            with open(config_path) as f:
                self.config = yaml.safe_load(f)
        else:
            # Fallback default configuration
            self.config = {
                'template_minimum': '3.11',
                'detection': {'enabled': True, 'increase_only': True},
                'env_overrides': {
                    'template_minimum': 'PYTHON_MIN_VERSION',
                    'detection_enabled': 'PYTHON_VERSION_DETECTION_ENABLED',
                    'increase_only': 'PYTHON_VERSION_INCREASE_ONLY'
                }
            }
        
        # Apply environment overrides
        self.template_minimum = self._parse_version(
            os.getenv(self.config['env_overrides']['template_minimum'], 
                     self.config['template_minimum'])
        )
        
        self.detection_enabled = self._parse_bool(
            os.getenv(self.config['env_overrides']['detection_enabled'], 'ON')
        )
        
        self.increase_only = self._parse_bool(
            os.getenv(self.config['env_overrides']['increase_only'], 'ON')
        )
        
    def _parse_version(self, version_str: str) -> Tuple[int, int]:
        """Parse version string into tuple."""
        try:
            parts = version_str.split('.')
            return (int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            print(f"Invalid version format: {version_str}, using default 3.11")
            return (3, 11)
    
    def _parse_bool(self, value: str) -> bool:
        """Parse boolean string (ON/OFF, True/False, 1/0)."""
        return value.upper() in ('ON', 'TRUE', '1', 'YES')
        
    def get_template_minimum(self) -> Tuple[int, int]:
        """Get the template/baseline minimum version."""
        return self.template_minimum
    
    def install_vermin(self) -> bool:
        """Install Vermin if not already available."""
        try:
            subprocess.run(['vermin', '--version'], 
                         capture_output=True, check=True)
            print("✓ Vermin already installed")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("Installing Vermin...")
            try:
                subprocess.run([sys.executable, '-m', 'pip', 'install', 'vermin'], 
                             check=True)
                print("✓ Vermin installed successfully")
                return True
            except subprocess.CalledProcessError as e:
                print(f"Failed to install Vermin: {e}")
                return False
    
    def detect_with_vermin(self) -> Optional[Tuple[int, int]]:
        """Use Vermin to detect minimum Python version from source code."""
        if not self.detection_enabled:
            print("Version detection is disabled")
            return None
            
        if not self.install_vermin():
            return None
        
        # Determine paths to analyze
        src_paths = []
        src_dir = self.project_root / 'src'
        if src_dir.exists():
            src_paths.append(str(src_dir))
        else:
            # Fallback to scanning project root but exclude common non-source dirs
            excludes = self.config.get('detection', {}).get('exclude_paths', [
                'tests/', '.venv/', 'build/', 'dist/', '.tmp/', '__pycache__/'
            ])
            # For now, just use project root - vermin has its own exclusion logic
            src_paths.append(str(self.project_root))
        
        for src_path in src_paths:
            try:
                print(f"Running Vermin analysis on: {src_path}")
                
                # Run vermin with parsable output for easier parsing
                result = subprocess.run([
                    'vermin', '--quiet', '--parsable', src_path
                ], capture_output=True, text=True, check=True)
                
                output = result.stdout.strip()
                if not output:
                    print("Vermin returned no version requirements")
                    continue
                
                # Parse vermin parsable output format
                # Typical output: "!2,3" or "2.7,3.6" or just "3.8"
                if ',' in output:
                    # Multiple versions listed, take the Python 3.x version
                    versions = output.split(',')
                    for version in versions:
                        version = version.strip()
                        if version.startswith('3.'):
                            major, minor = map(int, version.split('.'))
                            print(f"✓ Vermin detected minimum Python version: {major}.{minor}")
                            return (major, minor)
                else:
                    # Single version
                    if '.' in output:
                        major, minor = map(int, output.split('.'))
                        if major == 3:  # Only consider Python 3.x
                            print(f"✓ Vermin detected minimum Python version: {major}.{minor}")
                            return (major, minor)
                
            except subprocess.CalledProcessError as e:
                print(f"Vermin analysis failed for {src_path}: {e.stderr}")
                continue
            except ValueError as e:
                print(f"Could not parse Vermin output '{output}': {e}")
                continue
        
        print("Vermin analysis completed but no Python 3.x version detected")
        return None
    
    def _fallback_detection(self) -> Tuple[int, int]:
        """Fallback detection by analyzing imports and syntax."""
        print("Using fallback detection method...")
        
        # Look for f-strings, walrus operator, and other Python 3.6+ features
        features_found = {
            (3, 6): False,  # f-strings
            (3, 8): False,  # walrus operator :=
            (3, 9): False,  # dict merge |
            (3, 10): False, # match-case
            (3, 11): False, # exception groups
        }
        
        python_files = []
        src_path = self.project_root / 'src'
        if src_path.exists():
            python_files.extend(src_path.rglob('*.py'))
        else:
            python_files.extend(self.project_root.glob('*.py'))
            python_files.extend(self.project_root.glob('**/*.py'))
        
        for py_file in python_files:
            if 'test' in str(py_file) or '.venv' in str(py_file):
                continue
                
            try:
                content = py_file.read_text(encoding='utf-8')
                
                # Check for f-strings (3.6+)
                if re.search(r'f["\'].*\{.*\}', content):
                    features_found[(3, 6)] = True
                
                # Check for walrus operator (3.8+)
                if ':=' in content:
                    features_found[(3, 8)] = True
                
                # Check for dict merge (3.9+)
                if re.search(r'\|\s*\{', content):
                    features_found[(3, 9)] = True
                
                # Check for match-case (3.10+)
                if re.search(r'\bmatch\s+\w+:', content):
                    features_found[(3, 10)] = True
                    
                # Check for exception groups (3.11+)
                if 'except*' in content or 'ExceptionGroup' in content:
                    features_found[(3, 11)] = True
                    
            except Exception as e:
                print(f"Warning: Could not analyze {py_file}: {e}")
        
        # Find highest required version
        for version, found in reversed(list(features_found.items())):
            if found:
                print(f"✓ Fallback detected minimum Python version: {version[0]}.{version[1]}")
                return version
        
        # Default to Python 3.6 if no modern features found
        print("✓ No modern Python features detected, defaulting to 3.6")
        return (3, 6)
    
    def determine_project_minimum(self) -> Tuple[int, int]:
        """Determine the final minimum Python version for the project."""
        template_min = self.get_template_minimum()
        print(f"Template minimum version: {template_min[0]}.{template_min[1]}")
        
        if not self.detection_enabled:
            print("Detection disabled, using template minimum")
            return template_min
        
        detected = self.detect_with_vermin()
        if detected is None:
            print("No version detected by Vermin, using template minimum")
            return template_min
        
        print(f"Vermin detected minimum: {detected[0]}.{detected[1]}")
        
        # Apply increase-only policy
        if self.increase_only:
            if detected > template_min:
                print(f"✓ Using detected version {detected[0]}.{detected[1]} (higher than template)")
                return detected
            else:
                print(f"✓ Using template minimum {template_min[0]}.{template_min[1]} (higher than or equal to detected)")
                return template_min
        else:
            # Use detected version even if lower (rare case)
            print(f"✓ Using detected version {detected[0]}.{detected[1]} (increase-only disabled)")
            return detected
    
    def _update_pyproject_toml(self, version: Tuple[int, int]) -> bool:
        """Update pyproject.toml with new minimum version."""
        pyproject_path = self.project_root / 'pyproject.toml'
        if not pyproject_path.exists():
            return False
        
        content = pyproject_path.read_text()
        version_str = f"{version[0]}.{version[1]}"
        
        # Update requires-python
        content = re.sub(
            r'requires-python = "[^"]*"',
            f'requires-python = ">={version_str}"',
            content
        )
        
        # Update classifiers
        classifier_pattern = r'("Programming Language :: Python :: 3\.\d+")'
        classifiers = re.findall(classifier_pattern, content)
        
        # Remove versions below minimum
        for classifier in classifiers:
            match = re.search(r'3\.(\d+)', classifier)
            if match and int(match.group(1)) < version[1]:
                content = content.replace(f'    {classifier},\n', '')
        
        # Update mypy python_version
        content = re.sub(
            r'python_version = "[^"]*"',
            f'python_version = "{version_str}"',
            content
        )
        
        pyproject_path.write_text(content)
        print(f"✓ Updated pyproject.toml with minimum version {version_str}")
        return True
    
    def _update_github_workflow(self, version: Tuple[int, int]) -> bool:
        """Update GitHub workflow with new minimum version."""
        workflow_path = self.project_root / '.github/workflows/ci.yml'
        if not workflow_path.exists():
            return False
        
        content = workflow_path.read_text()
        version_str = f"{version[0]}.{version[1]}"
        
        # Update PYTHON_VERSION env var
        content = re.sub(
            r'PYTHON_VERSION: "[^"]*"',
            f'PYTHON_VERSION: "{version_str}"',
            content
        )
        
        # Update matrix versions - remove versions below minimum
        matrix_match = re.search(r'python-version: \[(.*?)\]', content, re.DOTALL)
        if matrix_match:
            versions_str = matrix_match.group(1)
            versions = re.findall(r'"(\d\.\d+)"', versions_str)
            
            # Filter versions >= minimum
            valid_versions = [v for v in versions 
                            if tuple(map(int, v.split('.'))) >= version]
            
            new_versions_str = ', '.join(f'"{v}"' for v in valid_versions)
            content = content.replace(
                versions_str.strip(), 
                new_versions_str
            )
        
        workflow_path.write_text(content)
        print(f"✓ Updated GitHub workflow with minimum version {version_str}")
        return True
    
    def _update_readthedocs(self, version: Tuple[int, int]) -> bool:
        """Update Read the Docs config with new minimum version."""
        rtd_path = self.project_root / '.readthedocs.yaml'
        if not rtd_path.exists():
            return False
        
        content = rtd_path.read_text()
        version_str = f"{version[0]}.{version[1]}"
        
        # Update Python version in build tools
        content = re.sub(
            r'python: "[^"]*"',
            f'python: "{version_str}"',
            content
        )
        
        rtd_path.write_text(content)
        print(f"✓ Updated Read the Docs config with minimum version {version_str}")
        return True
    
    def update_all_configs(self, version: Tuple[int, int]) -> Dict[str, bool]:
        """Update all configuration files with the new minimum version."""
        results = {}
        
        for config_file, update_func in self.config_files.items():
            if update_func is None:
                results[config_file] = True  # Skip read-only files
                continue
                
            try:
                results[config_file] = update_func(version)
            except Exception as e:
                print(f"Failed to update {config_file}: {e}")
                results[config_file] = False
        
        return results
    
    def generate_tox_config(self, version: Tuple[int, int]) -> bool:
        """Generate or update tox.ini with appropriate Python versions."""
        tox_path = self.project_root / 'tox.ini'
        
        # Generate list of Python versions to test
        min_version = version[1]  # Minor version
        max_version = 13  # Current latest
        
        test_versions = []
        for minor in range(min_version, max_version + 1):
            test_versions.append(f"py3{minor}")
        
        envlist = ','.join(test_versions)
        
        tox_config = f"""[tox]
envlist = {envlist}
minversion = 4.0
requires = tox>=4.0

[testenv]
deps = 
    pytest>=7.0.0
    pytest-cov>=4.0.0
commands = 
    pytest tests/ -v --cov=logreducer --cov-report=term-missing

[testenv:lint]
deps = 
    black>=23.0.0
    flake8>=6.0.0
    mypy>=1.0.0
commands =
    black --check src/
    flake8 src/
    mypy src/logreducer/

[testenv:docs]
deps = 
    -e.[docs]
commands =
    sphinx-build -b html docs/ docs/_build/html
"""
        
        tox_path.write_text(tox_config)
        print(f"✓ Generated tox.ini with test environments: {envlist}")
        return True
    
    def run_full_detection(self) -> Tuple[int, int]:
        """Run complete detection and update process."""
        print("=" * 60)
        print("Python Minimum Version Detection & Update")
        print("=" * 60)
        
        # Detect minimum version
        minimum_version = self.determine_project_minimum()
        
        print(f"\n📋 Project minimum Python version: {minimum_version[0]}.{minimum_version[1]}")
        
        # Update configuration files
        print("\n🔄 Updating configuration files...")
        results = self.update_all_configs(minimum_version)
        
        # Generate tox config
        self.generate_tox_config(minimum_version)
        
        # Report results
        print("\n📊 Update Results:")
        for config_file, success in results.items():
            status = "✓" if success else "❌"
            print(f"  {status} {config_file}")
        
        print(f"\n🎉 Detection complete! Project minimum: Python {minimum_version[0]}.{minimum_version[1]}")
        return minimum_version


def main():
    """Main entry point."""
    if len(sys.argv) > 1 and sys.argv[1] == '--help':
        print("Python Version Detector")
        print("Usage: python detect_python_version.py [--dry-run]")
        print("Environment variables:")
        print("  CICD_PYTHON_MIN: CI/CD minimum version (default: 3.11)")
        return
    
    detector = PythonVersionDetector()
    
    try:
        if len(sys.argv) > 1 and sys.argv[1] == '--dry-run':
            print("DRY RUN MODE - No files will be modified")
            minimum = detector.determine_project_minimum()
            print(f"Would set project minimum to: Python {minimum[0]}.{minimum[1]}")
        else:
            detector.run_full_detection()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nFatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()