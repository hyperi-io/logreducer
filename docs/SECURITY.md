# Security Policy

## Supported Versions

We actively maintain security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 3.1.x   | :white_check_mark: |
| 3.0.x   | :white_check_mark: |
| < 3.0   | :x:                |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability in LogReducer, please report it to us responsibly.

### How to Report

1. **Email**: Send details to security@hyperi.io with the subject line "LogReducer Security Vulnerability"
2. **Include**: 
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact assessment
   - Suggested fix (if any)

### What to Expect

- **Acknowledgment**: Within 24 hours
- **Initial Assessment**: Within 72 hours  
- **Regular Updates**: Every 7 days until resolved
- **Resolution Timeline**: Critical issues within 7 days, others within 30 days

### Security Features

LogReducer includes several security measures:

## Built-in Security Controls

### Input Validation
- File path sanitization to prevent directory traversal
- Input size limits to prevent resource exhaustion
- Character encoding validation to prevent injection attacks

### Memory Safety
- Bounded memory usage with configurable limits
- Safe streaming for large files without loading into memory
- Automatic cleanup of temporary resources

### Processing Isolation
- No execution of external commands from log data
- Pattern extraction uses safe parsing techniques
- Anomaly detection models are read-only during processing

## Security Scanning

Our CI/CD pipeline includes comprehensive security scanning:

### Automated Security Checks
- **Dependency Scanning**: Daily scans for known vulnerabilities in dependencies
- **Static Code Analysis**: Bandit and Semgrep for security issues in code
- **Secret Detection**: TruffleHog scans for hardcoded secrets
- **Code Quality**: CodeQL semantic analysis for security patterns
- **Container Security**: Trivy scans for container vulnerabilities

### Security Tools Configuration

#### Bandit Configuration
```toml
[tool.bandit]
exclude_dirs = ["tests", ".venv", "build", "dist", "data/samples"]
skips = ["B101", "B603"]  # Allow asserts in tests, controlled subprocess usage
```

#### Safety Configuration
```toml
# pip-audit configuration via CLI
ignore = []  # No ignored vulnerabilities
full_report = true
```

## Security Best Practices

### For Users

1. **Input Validation**
   - Always validate log file sources
   - Use absolute paths where possible
   - Set appropriate memory limits for your environment

2. **Access Control**
   - Run with minimal required privileges
   - Restrict file system access to necessary directories
   - Use dedicated service accounts in production

3. **Configuration Security**
   - Store sensitive configuration in environment variables
   - Use secure file permissions (600) for configuration files
   - Regular review and rotation of any authentication credentials

### For Developers

1. **Code Security**
   - Run security scans before committing: `bandit -r src/`
   - Check dependencies regularly: `pip-audit`
   - Use type hints to prevent common bugs

2. **Testing**
   - Include security test cases
   - Test with malformed and malicious inputs
   - Verify resource cleanup in error conditions

## Vulnerability Management

### Response Process

1. **Triage**: Assess severity using CVSS scoring
2. **Investigation**: Reproduce and understand the issue
3. **Development**: Create and test fix
4. **Testing**: Comprehensive security testing of fix
5. **Release**: Coordinated disclosure and patch release
6. **Communication**: Security advisory to users

### Severity Classification

- **Critical**: Remote code execution, authentication bypass
- **High**: Local privilege escalation, sensitive data exposure
- **Medium**: Denial of service, information disclosure
- **Low**: Security hardening opportunities

## Security Updates

### Notification Channels
- GitHub Security Advisories
- Release notes highlighting security fixes
- Direct communication for critical vulnerabilities

### Update Recommendations
- Apply security updates within 7 days for critical issues
- Apply security updates within 30 days for high/medium issues
- Subscribe to security notifications for timely updates

## Compliance

LogReducer is designed to support security compliance requirements:

### Data Protection
- No data is transmitted externally without explicit configuration
- Log data processing is performed locally
- Temporary files are securely cleaned up

### Audit Trail
- Processing statistics and metadata are logged
- Configuration changes are tracked
- Error conditions are properly logged for investigation

## Contact Information

- **Security Team**: security@hyperi.io
- **General Support**: support@hyperi.io
- **Documentation**: https://hyperi-io.github.io/logreducer/

---

*This security policy is reviewed quarterly and updated as needed to reflect current best practices and threat landscape.*