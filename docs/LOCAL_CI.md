# Local CI/CD Pipeline

## Overview

LogReducer uses a **local-first CI/CD approach** where all CI steps run locally by default. GitHub Actions is only used for JFrog Artifactory deployment when explicitly configured.

## Philosophy

- **Local Development = CI Environment**: What runs locally is exactly what runs in CI
- **Fast Feedback**: No waiting for GitHub Actions runners
- **Cost Efficient**: Minimize GitHub Actions usage
- **Full Control**: Run CI on your own hardware
- **Optional Cloud**: JFrog deployment remains in GitHub Actions for security

## Quick Start

### Run Full CI Pipeline Locally

```bash
# Run complete CI pipeline
make ci

# Run CI without slow tests (faster)
make ci-fast

# Run CI and deploy to JFrog (requires credentials)
make ci-deploy
```

### Individual CI Stages

```bash
# Run specific stages
scripts/local-ci --stage test      # Run tests only
scripts/local-ci --stage lint      # Run linting only
scripts/local-ci --stage security  # Run security scan only
scripts/local-ci --stage build     # Build packages only
scripts/local-ci --stage deploy    # Deploy to JFrog only
```

## Configuration

### Environment Variables

Control CI behavior with environment variables:

```bash
# Security level (NONE, LOW, MEDIUM, HIGH, CRITICAL)
export MIN_SECURITY_LEVEL=NONE

# JFrog Artifactory credentials (stored in GitHub Secrets, not locally)
# ARTIFACTORY_USER and ARTIFACTORY_TOKEN are in GitHub Secrets
# Repository URL: https://hypersec.jfrog.io/artifactory/api/pypi/hypersec-pypi-local/

# Run CI with custom settings
MIN_SECURITY_LEVEL=LOW make ci
```

**Note**: JFrog Artifactory credentials (`ARTIFACTORY_USER` and `ARTIFACTORY_TOKEN`) are stored in GitHub Secrets for security. Local deployments should use GitHub Actions for secure credential handling.

### GitHub Actions Variables

When using GitHub Actions, set these repository variables:

- `USE_GITHUB_ACTIONS`: Set to `true` to use GitHub Actions instead of local CI
- `AUTO_DEPLOY_TO_JFROG`: Set to `true` to auto-deploy on main branch
- `MIN_SECURITY_LEVEL`: Security threshold (default: NONE)
- `ARTIFACTORY_URL`: JFrog repository URL

### CI Configuration File

Edit `.github/ci-config.yml` to customize CI behavior:

```yaml
ci:
  runner: local  # or 'github' for GitHub Actions
  deployment:
    auto_deploy: false
  security:
    min_level: NONE
  tests:
    run_slow_tests: false
```

## Local CI Pipeline Stages

The local CI pipeline runs these stages in order:

1. **Version Check**: Ensure version consistency across files
2. **Editable Install Test**: Verify PEP 660 compatibility
3. **Linting & Formatting**: Black, Flake8, MyPy
4. **Testing**: Unit and integration tests with coverage
5. **Security Scanning**: pip-audit, Bandit, Semgrep
6. **Build**: Create wheel and sdist packages
7. **Deploy** (optional): Upload to JFrog Artifactory

## CI Pipeline Output

```
[START] Starting Local CI Pipeline
Project: logreducer
Version: 3.2.1
Python: 3.12

============================================================
STAGE: Version Verification
============================================================
[PASS] Version Consistency Check passed (2.3s)

============================================================
STAGE: Testing
============================================================
[PASS] Unit Tests passed (15.2s)
[PASS] Integration Tests (Fast) passed (23.5s)

============================================================
CI PIPELINE SUMMARY
============================================================
[PASS]    Version Consistency Check    (2.3s)
[PASS]    Editable Install Test         (1.5s)
[PASS]    Black Format Check            (0.8s)
[PASS]    Flake8 (Critical)             (0.5s)
[PASS]    Unit Tests                    (15.2s)
[PASS]    Integration Tests (Fast)      (23.5s)
[PASS]    Security Scan                 (45.3s)
[PASS]    Build Packages                (3.2s)
------------------------------------------------------------
Total: 8 passed, 0 failed
Duration: 92.3 seconds
[PASS] CI PIPELINE PASSED
```

## GitHub Actions Integration

### Manual JFrog Deployment

Deploy to JFrog using GitHub Actions workflow:

```bash
# Trigger deployment workflow manually
gh workflow run deploy-jfrog.yml \
  -f deploy_environment=production \
  -f skip_ci=false
```

### Automatic Deployment

Set `AUTO_DEPLOY_TO_JFROG=true` in repository variables to enable automatic deployment on main branch pushes.

### Switching to GitHub Actions

To use GitHub Actions instead of local CI:

1. Set repository variable: `USE_GITHUB_ACTIONS=true`
2. Push changes to trigger workflow
3. CI will run in GitHub Actions instead of locally

## Advantages of Local CI

### Speed
- No queue waiting
- No runner startup time
- Instant feedback

### Cost
- Zero GitHub Actions minutes used
- No self-hosted runner costs
- Use your existing hardware

### Privacy
- Code never leaves your machine
- No exposure to cloud services
- Full control over environment

### Debugging
- Direct access to failed state
- Interactive debugging possible
- No artifact download needed

## Comparison: Local vs GitHub Actions

| Feature | Local CI | GitHub Actions |
|---------|----------|----------------|
| Speed | [FAST] Instant | [SLOW] 2-5 min queue |
| Cost | [FREE] Free | [COST] Minutes/runners |
| Privacy | [LOCAL] Local only | [CLOUD] Cloud |
| Debugging | [DIRECT] Direct | [REMOTE] Via artifacts |
| Scalability | [LIMITED] Single machine | [SCALE] Unlimited |
| JFrog Deploy | [MANUAL] Manual creds | [SECURE] Secure secrets |

## Best Practices

1. **Development**: Always run `make ci-fast` before pushing
2. **Pre-commit**: Use `make all` for complete validation
3. **Security**: Keep `MIN_SECURITY_LEVEL=NONE` for zero tolerance
4. **Deployment**: Use GitHub Actions for JFrog (secure secrets)
5. **Testing**: Run slow tests locally periodically

## Troubleshooting

### Virtual Environment Not Found
```bash
# Setup environment first
scripts/setup
```

### Security Scan Fails
```bash
# Check security level
MIN_SECURITY_LEVEL=LOW make ci
```

### JFrog Deployment Fails
```bash
# Credentials are in GitHub Secrets, not local environment
# Use GitHub Actions for secure deployment:
gh workflow run deploy-jfrog.yml \
  -f deploy_environment=production \
  -f skip_ci=false

# For local testing only (not recommended for production):
export ARTIFACTORY_USER=xxx
export ARTIFACTORY_TOKEN=yyy
twine upload --repository-url https://hypersec.jfrog.io/artifactory/api/pypi/hypersec-pypi-local/ dist/* --verbose
```

### CI Takes Too Long
```bash
# Skip slow tests
make ci-fast

# Run specific stage
scripts/local-ci --stage test
```

## Migration from GitHub Actions

If migrating from pure GitHub Actions:

1. **Install dependencies locally**:
   ```bash
   scripts/setup
   ```

2. **Test local CI**:
   ```bash
   make ci-fast
   ```

3. **Configure JFrog credentials** (if needed):
   ```bash
   export ARTIFACTORY_USERNAME=xxx
   export ARTIFACTORY_PASSWORD=yyy
   ```

4. **Update repository settings**:
   - Set `USE_GITHUB_ACTIONS=false`
   - Configure `AUTO_DEPLOY_TO_JFROG` as needed

## Future Enhancements

- [ ] Distributed local CI across multiple machines
- [ ] Docker container for consistent environment
- [ ] CI result caching between runs
- [ ] Parallel test execution
- [ ] Progressive deployment strategies
- [ ] Webhook notifications for CI results

## Summary

The local-first CI approach provides fast, cost-effective, and private continuous integration while maintaining the option to use GitHub Actions for secure deployments to JFrog Artifactory. This hybrid model gives you the best of both worlds: speed and control locally, with secure cloud deployment when needed.
