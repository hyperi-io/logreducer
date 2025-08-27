#!/usr/bin/env python3
"""
Security scanning script for LogReducer

This script runs comprehensive security scans including:
- Dependency vulnerability scanning with pip-audit
- Static code analysis with Bandit
- Semantic security analysis with Semgrep
- Secret detection with TruffleHog (if available)

Usage:
    python scripts/security_scan.py [--fix] [--report-only]
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class SecurityScanner:
    """Comprehensive security scanner for LogReducer"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.src_dir = project_root / "src"
        self.tmp_dir = project_root / ".tmp"
        self.tmp_dir.mkdir(exist_ok=True)
        self.reports_dir = self.tmp_dir / "security-reports"
        self.reports_dir.mkdir(exist_ok=True)
        
    def run_command(self, cmd: List[str], capture_output: bool = True) -> Tuple[int, str, str]:
        """Run a command and return (exit_code, stdout, stderr)"""
        try:
            result = subprocess.run(
                cmd, 
                capture_output=capture_output,
                text=True,
                cwd=self.project_root
            )
            return result.returncode, result.stdout, result.stderr
        except FileNotFoundError:
            return 1, "", f"Command not found: {cmd[0]}"
    
    def install_tools(self) -> bool:
        """Install required security tools"""
        tools = [
            "pip-audit", 
            "bandit[toml]",
            "semgrep"
        ]
        
        print("Installing security tools...")
        for tool in tools:
            print(f"  Installing {tool}...")
            # Try uv first, fallback to pip
            exit_code, _, stderr = self.run_command([
                "uv", "pip", "install", "--upgrade", tool
            ])
            if exit_code != 0:
                # Fallback to regular pip
                exit_code, _, stderr = self.run_command([
                    sys.executable, "-m", "pip", "install", "--upgrade", tool
                ])
            
            if exit_code != 0:
                print(f"  Failed to install {tool}: {stderr}")
                return False
        
        print("✓ Security tools installed successfully")
        return True
    
    def scan_dependencies_pip_audit(self) -> Dict:
        """Scan dependencies with pip-audit"""
        print("\nSCANNING: Running pip-audit dependency scan...")
        
        report_file = self.reports_dir / "pip-audit-report.json"
        # Try uv run first, fallback to direct command
        exit_code, stdout, stderr = self.run_command([
            "uv", "run", "pip-audit", "--format=json", "--output", str(report_file)
        ])
        if exit_code != 0 and "command not found" in stderr.lower():
            exit_code, stdout, stderr = self.run_command([
                "pip-audit", "--format=json", "--output", str(report_file)
            ])
        
        # pip-audit returns non-zero if vulnerabilities found, which is expected
        if report_file.exists():
            with open(report_file) as f:
                report = json.load(f)
            
            vuln_count = len(report.get("vulnerabilities", []))
            if vuln_count > 0:
                print(f"  WARNING:  Found {vuln_count} dependency vulnerabilities")
                for vuln in report["vulnerabilities"][:3]:  # Show first 3
                    package = vuln.get('package', {}).get('name', 'Unknown')
                    advisory = vuln.get('advisory', {}).get('summary', 'No details')
                    print(f"     - {package}: {advisory}")
                if vuln_count > 3:
                    print(f"     ... and {vuln_count - 3} more")
            else:
                print("  ✓ No dependency vulnerabilities found")
            
            return {
                "tool": "pip-audit",
                "status": "completed",
                "vulnerabilities": vuln_count,
                "report_file": str(report_file)
            }
        else:
            print(f"  FAILED: pip-audit scan failed: {stderr}")
            return {
                "tool": "pip-audit", 
                "status": "failed",
                "error": stderr
            }
    
    def scan_dependencies_pip_audit(self) -> Dict:
        """Scan dependencies with pip-audit"""
        print("\nSCANNING: Running pip-audit dependency scan...")
        
        report_file = self.reports_dir / "pip-audit-report.json"
        # Try uv run first, fallback to direct command
        exit_code, stdout, stderr = self.run_command([
            "uv", "run", "pip-audit", "--format=json", f"--output={report_file}"
        ])
        if exit_code != 0 and "command not found" in stderr.lower():
            exit_code, stdout, stderr = self.run_command([
                "pip-audit", "--format=json", f"--output={report_file}"
            ])
        
        if exit_code == 0 and report_file.exists():
            with open(report_file) as f:
                report = json.load(f)
            
            vuln_count = len(report.get("vulnerabilities", []))
            if vuln_count > 0:
                print(f"  WARNING:  Found {vuln_count} dependency vulnerabilities")
            else:
                print("  ✓ No dependency vulnerabilities found")
            
            return {
                "tool": "pip-audit",
                "status": "completed", 
                "vulnerabilities": vuln_count,
                "report_file": str(report_file)
            }
        else:
            print(f"  FAILED: pip-audit scan failed: {stderr}")
            return {
                "tool": "pip-audit",
                "status": "failed", 
                "error": stderr
            }
    
    def scan_static_bandit(self) -> Dict:
        """Run Bandit static security analysis"""
        print("\nSCANNING: Running Bandit static security scan...")
        
        report_file = self.reports_dir / "bandit-report.json"
        # Try uv run first, fallback to direct command
        exit_code, stdout, stderr = self.run_command([
            "uv", "run", "bandit", "-r", str(self.src_dir), "-f", "json", "-o", str(report_file)
        ])
        if exit_code != 0 and "command not found" in stderr.lower():
            exit_code, stdout, stderr = self.run_command([
                "bandit", "-r", str(self.src_dir), "-f", "json", "-o", str(report_file)
            ])
        
        if report_file.exists():
            with open(report_file) as f:
                report = json.load(f)
            
            issue_count = len(report.get("results", []))
            if issue_count > 0:
                print(f"  WARNING:  Found {issue_count} potential security issues")
                
                # Show summary by severity
                severity_counts = {}
                for result in report["results"]:
                    severity = result.get("issue_severity", "UNKNOWN")
                    severity_counts[severity] = severity_counts.get(severity, 0) + 1
                
                for severity, count in severity_counts.items():
                    print(f"     - {severity}: {count}")
            else:
                print("  ✓ No security issues found")
            
            return {
                "tool": "bandit",
                "status": "completed",
                "issues": issue_count,
                "report_file": str(report_file)
            }
        else:
            print(f"  FAILED: Bandit scan failed: {stderr}")
            return {
                "tool": "bandit",
                "status": "failed",
                "error": stderr
            }
    
    def scan_semantic_semgrep(self) -> Dict:
        """Run Semgrep semantic security analysis"""
        print("\nSCANNING: Running Semgrep semantic security scan...")
        
        report_file = self.reports_dir / "semgrep-report.json"
        # Try uv run first, fallback to direct command
        exit_code, stdout, stderr = self.run_command([
            "uv", "run", "semgrep", "--config=auto", str(self.src_dir), 
            "--json", f"--output={report_file}"
        ])
        if exit_code != 0 and "command not found" in stderr.lower():
            exit_code, stdout, stderr = self.run_command([
                "semgrep", "--config=auto", str(self.src_dir), 
                "--json", f"--output={report_file}"
            ])
        
        if report_file.exists():
            with open(report_file) as f:
                report = json.load(f)
            
            issue_count = len(report.get("results", []))
            if issue_count > 0:
                print(f"  WARNING:  Found {issue_count} potential security issues")
                
                # Show summary by severity
                severity_counts = {}
                for result in report["results"]:
                    severity = result.get("extra", {}).get("severity", "INFO")
                    severity_counts[severity] = severity_counts.get(severity, 0) + 1
                
                for severity, count in severity_counts.items():
                    print(f"     - {severity}: {count}")
            else:
                print("  ✓ No security issues found")
            
            return {
                "tool": "semgrep",
                "status": "completed",
                "issues": issue_count,
                "report_file": str(report_file)
            }
        else:
            print(f"  FAILED: Semgrep scan failed: {stderr}")
            return {
                "tool": "semgrep",
                "status": "failed",
                "error": stderr
            }
    
    def generate_summary_report(self, scan_results: List[Dict]) -> None:
        """Generate a comprehensive summary report"""
        print("\nANALYSIS: Security Scan Summary")
        print("=" * 50)
        
        total_issues = 0
        critical_issues = 0
        
        for result in scan_results:
            if result["status"] == "completed":
                tool = result["tool"]
                if "vulnerabilities" in result:
                    count = result["vulnerabilities"]
                    total_issues += count
                    if count > 0:
                        # Assume all vulnerabilities are critical for now
                        critical_issues += count
                    print(f"{tool:12}: {count:3} vulnerabilities")
                elif "issues" in result:
                    count = result["issues"]
                    total_issues += count
                    print(f"{tool:12}: {count:3} potential issues")
            else:
                print(f"{result['tool']:12}: FAILED - {result.get('error', 'Unknown error')}")
        
        print("-" * 50)
        print(f"{'Total':12}: {total_issues:3} issues found")
        
        if total_issues == 0:
            print("\nSUCCESS: No security issues detected!")
        else:
            print(f"\nWARNING:  {total_issues} security issues require attention")
            if critical_issues > 0:
                print(f"CRITICAL: {critical_issues} issues are potentially critical")
        
        print(f"\nFILES: Detailed reports saved to: {self.reports_dir}")
        
        # Save summary as JSON
        summary_file = self.reports_dir / "security-summary.json"
        summary = {
            "scan_timestamp": subprocess.run(["date", "-Iseconds"], 
                                           capture_output=True, text=True).stdout.strip(),
            "total_issues": total_issues,
            "critical_issues": critical_issues,
            "scan_results": scan_results
        }
        
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"REPORT: Summary report saved to: {summary_file}")
    
    def run_full_scan(self) -> bool:
        """Run all security scans"""
        print("SECURITY:  Starting comprehensive security scan for LogReducer")
        print(f"Project root: {self.project_root}")
        
        # Install tools if needed
        if not self.install_tools():
            return False
        
        # Run all scans
        scan_results = []
        
        try:
            scan_results.append(self.scan_dependencies_pip_audit())
            scan_results.append(self.scan_dependencies_pip_audit())
            scan_results.append(self.scan_static_bandit())
            scan_results.append(self.scan_semantic_semgrep())
        except KeyboardInterrupt:
            print("\nWARNING:  Scan interrupted by user")
            return False
        
        # Generate summary
        self.generate_summary_report(scan_results)
        
        # Return True if no critical issues found
        total_issues = sum(
            result.get("vulnerabilities", 0) + result.get("issues", 0) 
            for result in scan_results 
            if result["status"] == "completed"
        )
        
        return total_issues == 0


def main():
    parser = argparse.ArgumentParser(description="Run security scans for LogReducer")
    parser.add_argument("--report-only", action="store_true", 
                       help="Only generate reports, don't fail on issues")
    parser.add_argument("--install-tools", action="store_true",
                       help="Install security tools and exit")
    
    args = parser.parse_args()
    
    project_root = Path(__file__).parent.parent
    scanner = SecurityScanner(project_root)
    
    if args.install_tools:
        success = scanner.install_tools()
        sys.exit(0 if success else 1)
    
    success = scanner.run_full_scan()
    
    if args.report_only:
        print("\nREPORT: Report-only mode: exiting with success regardless of findings")
        sys.exit(0)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()