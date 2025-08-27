#!/usr/bin/env python3
"""
Developer Tools Check Script for LogReducer

This script verifies that all required development tools are installed
and provides guidance for setting up the development environment.

Usage:
    python scripts/check_dev_tools.py [--install] [--vm-info]
    
Options:
    --install   Show installation commands for missing tools
    --vm-info   Show dfe-fedora-desktop VM setup information
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class DevToolsChecker:
    """Check and validate development environment tools"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.missing_tools = []
        self.warnings = []
        
        # Required tools with version checks
        self.required_tools = {
            # Core Python tools
            "python3": {
                "command": ["python3", "--version"],
                "min_version": "3.12.0",
                "install_fedora": "sudo dnf install python3 python3-devel",
                "install_ubuntu": "sudo apt update && sudo apt install python3 python3-dev",
                "description": "Python 3.12+ interpreter"
            },
            "uv": {
                "command": ["uv", "--version"], 
                "min_version": "0.1.0",
                "install_fedora": "curl -LsSf https://astral.sh/uv/install.sh | sh",
                "install_ubuntu": "curl -LsSf https://astral.sh/uv/install.sh | sh",
                "description": "Fast Python package installer and resolver"
            },
            
            # Git and version control
            "git": {
                "command": ["git", "--version"],
                "min_version": "2.34.0",
                "install_fedora": "sudo dnf install git git-lfs",
                "install_ubuntu": "sudo apt install git git-lfs",
                "description": "Git version control system"
            },
            "git-lfs": {
                "command": ["git-lfs", "version"],
                "min_version": "3.0.0",
                "install_fedora": "sudo dnf install git-lfs",
                "install_ubuntu": "sudo apt install git-lfs",
                "description": "Git Large File Storage"
            },
            
            # GitHub CLI
            "gh": {
                "command": ["gh", "--version"],
                "min_version": "2.0.0",
                "install_fedora": "sudo dnf install gh",
                "install_ubuntu": "sudo apt install gh",
                "description": "GitHub CLI for repository management"
            },
            
            # Node.js for Husky hooks
            "node": {
                "command": ["node", "--version"],
                "min_version": "18.0.0", 
                "install_fedora": "sudo dnf install nodejs npm",
                "install_ubuntu": "sudo apt install nodejs npm",
                "description": "Node.js runtime for commit hooks"
            },
            "npm": {
                "command": ["npm", "--version"],
                "min_version": "8.0.0",
                "install_fedora": "sudo dnf install npm",
                "install_ubuntu": "sudo apt install npm", 
                "description": "Node Package Manager"
            }
        }
        
        # Optional but recommended tools
        self.optional_tools = {
            "code": {
                "command": ["code", "--version"],
                "description": "Visual Studio Code editor",
                "install_fedora": "sudo dnf install code",
                "install_ubuntu": "sudo apt install code"
            },
            "docker": {
                "command": ["docker", "--version"], 
                "description": "Docker containerization platform",
                "install_fedora": "sudo dnf install docker docker-compose",
                "install_ubuntu": "sudo apt install docker.io docker-compose"
            }
        }
    
    def run_command(self, cmd: List[str], capture_output: bool = True) -> Tuple[int, str, str]:
        """Run a command and return (exit_code, stdout, stderr)"""
        try:
            result = subprocess.run(
                cmd, 
                capture_output=capture_output,
                text=True,
                timeout=10
            )
            return result.returncode, result.stdout.strip(), result.stderr.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return 1, "", f"Command not found: {' '.join(cmd)}"
    
    def parse_version(self, version_str: str) -> Optional[Tuple[int, ...]]:
        """Parse version string into tuple for comparison"""
        try:
            # Extract version numbers from various formats
            import re
            version_match = re.search(r'(\d+)\.(\d+)\.(\d+)', version_str)
            if version_match:
                return tuple(int(x) for x in version_match.groups())
        except Exception:
            pass
        return None
    
    def check_tool(self, name: str, tool_info: dict) -> bool:
        """Check if a specific tool is installed and meets version requirements"""
        print(f"🔍 Checking {name}...")
        
        # Check if tool exists
        if not shutil.which(name):
            print(f"   ❌ {name} not found in PATH")
            return False
        
        # Run version check
        exit_code, stdout, stderr = self.run_command(tool_info["command"])
        if exit_code != 0:
            print(f"   ❌ Failed to get {name} version: {stderr}")
            return False
        
        # Parse and check version
        if "min_version" in tool_info:
            current_version = self.parse_version(stdout)
            required_version = self.parse_version(tool_info["min_version"])
            
            if current_version and required_version:
                if current_version < required_version:
                    print(f"   ⚠️  {name} version {'.'.join(map(str, current_version))} < required {tool_info['min_version']}")
                    self.warnings.append(f"{name} version is below recommended minimum")
                    return True  # Still usable, just warn
                else:
                    print(f"   ✅ {name} version {'.'.join(map(str, current_version))} OK")
            else:
                print(f"   ⚠️  Could not parse {name} version: {stdout}")
                self.warnings.append(f"Could not verify {name} version")
        else:
            print(f"   ✅ {name} available")
        
        return True
    
    def check_python_environment(self) -> bool:
        """Check Python virtual environment setup"""
        print("\n🐍 Checking Python Environment...")
        
        venv_path = self.project_root / ".venv"
        if not venv_path.exists():
            print("   ❌ Virtual environment not found at .venv")
            print("   💡 Run: uv venv .venv && source .venv/bin/activate")
            return False
        
        print("   ✅ Virtual environment found")
        
        # Check if packages are installed
        activate_script = venv_path / "bin" / "activate"
        if not activate_script.exists():
            print("   ⚠️  Virtual environment may be corrupted")
            self.warnings.append("Virtual environment may need recreation")
        else:
            print("   ✅ Virtual environment appears valid")
        
        return True
    
    def check_git_setup(self) -> bool:
        """Check Git configuration"""
        print("\n📋 Checking Git Setup...")
        
        # Check git config
        exit_code, stdout, _ = self.run_command(["git", "config", "user.name"])
        if exit_code != 0 or not stdout:
            print("   ❌ Git user.name not configured")
            print("   💡 Run: git config --global user.name 'Your Name'")
            return False
        
        exit_code, stdout, _ = self.run_command(["git", "config", "user.email"])
        if exit_code != 0 or not stdout:
            print("   ❌ Git user.email not configured")
            print("   💡 Run: git config --global user.email 'your.email@company.com'")
            return False
        
        # Check if in git repository
        exit_code, _, _ = self.run_command(["git", "status"])
        if exit_code != 0:
            print("   ❌ Not in a Git repository")
            return False
        
        # Check Git LFS
        exit_code, _, _ = self.run_command(["git", "lfs", "status"])
        if exit_code != 0:
            print("   ⚠️  Git LFS not initialized")
            print("   💡 Run: git lfs install")
            self.warnings.append("Git LFS should be initialized")
        else:
            print("   ✅ Git LFS initialized")
        
        print("   ✅ Git configuration OK")
        return True
    
    def check_husky_setup(self) -> bool:
        """Check Husky commit hooks setup"""
        print("\n🐕 Checking Husky Setup...")
        
        husky_dir = self.project_root / ".husky"
        if not husky_dir.exists():
            print("   ❌ Husky hooks not found")
            print("   💡 Run: npm install && npx husky install")
            return False
        
        required_hooks = ["pre-commit", "pre-push", "commit-msg"]
        for hook in required_hooks:
            hook_path = husky_dir / hook
            if not hook_path.exists():
                print(f"   ❌ Missing {hook} hook")
                return False
            elif not hook_path.is_file():
                print(f"   ❌ {hook} is not a file")
                return False
        
        print("   ✅ All Husky hooks present")
        return True
    
    def show_installation_guide(self, distro: str = "fedora") -> None:
        """Show installation commands for missing tools"""
        if not self.missing_tools:
            return
        
        print(f"\n📦 Installation Guide ({distro}):")
        print("=" * 50)
        
        for tool_name in self.missing_tools:
            if tool_name in self.required_tools:
                tool_info = self.required_tools[tool_name]
                install_key = f"install_{distro}"
                if install_key in tool_info:
                    print(f"\n• {tool_name}: {tool_info['description']}")
                    print(f"  {tool_info[install_key]}")
        
        print(f"\n🔧 After installing tools:")
        print("1. Restart your shell or source ~/.bashrc")
        print("2. Run this check again: python scripts/check_dev_tools.py")
        print("3. Setup Python environment: uv venv .venv")
        print("4. Install dependencies: uv pip install -e \".[dev,enhanced]\"")
        print("5. Initialize Git LFS: git lfs install")
        print("6. Install commit hooks: npm install && npx husky install")
    
    def show_vm_info(self) -> None:
        """Show dfe-fedora-desktop VM setup information"""
        print("\n🖥️  DFE Fedora Desktop VM Setup:")
        print("=" * 50)
        print("""
The dfe-fedora-desktop VM comes pre-configured with most development tools.

To get started:

1. Clone the repository:
   git clone https://github.com/hypersec-io/logreducer.git
   cd logreducer

2. Check tools (should mostly pass):
   python scripts/check_dev_tools.py

3. Setup Python environment:
   uv venv .venv
   source .venv/bin/activate
   uv pip install -e ".[dev,enhanced]"

4. Initialize Git LFS and hooks:
   git lfs install
   npm install && npx husky install

5. Run tests to verify setup:
   pytest tests/ -v

6. Start development!

VM Benefits:
- ✅ All required tools pre-installed
- ✅ Proper development environment configured  
- ✅ Security tools and scanning available
- ✅ VS Code with extensions ready
- ✅ Docker and container tools available

For VM access, contact your system administrator.
        """)
    
    def run_checks(self) -> bool:
        """Run all development environment checks"""
        print("🚀 LogReducer Development Environment Check")
        print("=" * 50)
        
        all_good = True
        
        # Check required tools
        print("\n📋 Required Tools:")
        for name, tool_info in self.required_tools.items():
            if not self.check_tool(name, tool_info):
                self.missing_tools.append(name)
                all_good = False
        
        # Check optional tools
        print("\n🔧 Optional Tools:")
        for name, tool_info in self.optional_tools.items():
            self.check_tool(name, tool_info)  # Don't fail for optional
        
        # Environment checks
        if not self.check_python_environment():
            all_good = False
        
        if not self.check_git_setup():
            all_good = False
        
        if not self.check_husky_setup():
            all_good = False
        
        # Summary
        print("\n" + "=" * 50)
        if all_good and not self.warnings:
            print("✅ All checks passed! Development environment ready.")
            print("\n🚀 Next steps:")
            print("1. Activate venv: source .venv/bin/activate")  
            print("2. Run tests: pytest tests/ -v")
            print("3. Start coding!")
        elif all_good and self.warnings:
            print("WARNING: Environment mostly ready with some warnings:")
            for warning in self.warnings:
                print(f"   • {warning}")
            print("\nSUCCESS: You can proceed with development.")
        else:
            print("ERROR: Development environment needs setup.")
            print(f"\n{len(self.missing_tools)} required tools missing.")
            all_good = False
        
        return all_good


def main():
    parser = argparse.ArgumentParser(
        description="Check LogReducer development environment"
    )
    parser.add_argument(
        "--install", 
        action="store_true",
        help="Show installation commands for missing tools"
    )
    parser.add_argument(
        "--vm-info",
        action="store_true", 
        help="Show dfe-fedora-desktop VM setup information"
    )
    parser.add_argument(
        "--distro",
        choices=["fedora", "ubuntu"],
        default="fedora",
        help="Distribution for install commands"
    )
    
    args = parser.parse_args()
    
    checker = DevToolsChecker()
    
    if args.vm_info:
        checker.show_vm_info()
        return 0
    
    # Run the checks
    success = checker.run_checks()
    
    if args.install and checker.missing_tools:
        checker.show_installation_guide(args.distro)
    
    # Exit with appropriate code
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())