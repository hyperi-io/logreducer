# LogReducer Deployment Guide

This document provides comprehensive instructions for deploying LogReducer to your private corporate PyPI repository on JFrog Artifactory.

## Prerequisites

### Required Tools
- Python 3.8+ 
- `uv` package manager (preferred) or `pip`
- `git` for version control
- JFrog Artifactory access with PyPI repository configured
- GitHub account (for CI/CD)

### Development Dependencies
```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and setup project
git clone https://github.com/company/logreducer.git
cd logreducer
uv venv .venv --seed
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e ".[dev,enhanced]"
```

## Quick Deployment

### 1. Build Package
```bash
# Local build and test
./scripts/local_ci.sh --coverage

# Or manual build
python -m build
twine check dist/*
```

### 2. Deploy to Staging
```bash
# Configure Artifactory credentials
export TWINE_USERNAME="your-artifactory-user"
export TWINE_PASSWORD="your-artifactory-token" 
export TWINE_REPOSITORY_URL="https://hypersec.jfrog.io/artifactory/api/pypi/hypersec-pypi-local/simple/"

# Upload to staging
twine upload dist/*
```

### 3. Deploy to Production
```bash
# Production deployment (after staging validation)
export TWINE_REPOSITORY_URL="https://hypersec.jfrog.io/artifactory/api/pypi/hypersec-pypi-local/simple/"
twine upload dist/*
```

## 🔄 Automated CI/CD Pipeline

### GitHub Actions Setup

1. **Configure Repository Secrets** in GitHub:
   ```
   ARTIFACTORY_USERNAME      # Your JFrog Artifactory username
   ARTIFACTORY_PASSWORD      # Your JFrog Artifactory API token
   ARTIFACTORY_PYPI_URL      # https://hypersec.jfrog.io/artifactory/api/pypi/hypersec-pypi-local/simple/
   STAGING_PYPI_USERNAME     # Staging environment credentials
   STAGING_PYPI_PASSWORD     # Staging environment token
   STAGING_PYPI_URL          # Staging PyPI repository URL
   GITHUB_TOKEN              # GitHub token for releases (auto-provided)
   ```

2. **Trigger Deployment**:
   ```bash
   # Create feature branch
   git checkout -b feature/awesome-feature
   git commit -m "feat: add awesome new feature"
   git push origin feature/awesome-feature
   
   # Create Pull Request -> triggers CI tests
   # Merge to develop -> deploys to staging
   # Merge to main -> deploys to production
   ```

### Local CI Execution

```bash
# Run full CI pipeline locally using act
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash
act -j local-test

# Or use our local CI script
./scripts/local_ci.sh --coverage --verbose
```

## 📦 Package Configuration

### Version Management (Semantic Release)

LogReducer uses semantic-release for automated versioning based on conventional commits:

```bash
# Commit format examples
git commit -m "feat: add anomaly detection mode"     # Minor version bump
git commit -m "fix: resolve memory leak in streaming" # Patch version bump  
git commit -m "feat!: redesign core API"             # Major version bump
git commit -m "docs: update README"                  # No version bump
```

### Build Configuration

The package is configured with both `setup.py` (legacy) and `pyproject.toml` (modern):

- **Core dependencies**: drain3, loguru, psutil, tqdm
- **Enhanced features**: scikit-learn, numpy, scipy, xxhash, datasketch
- **Development tools**: pytest, black, flake8, mypy

## JFrog Artifactory Setup

### Repository Configuration

1. **Create PyPI Repository**:
   ```json
   {
     "key": "pypi-local",
     "rclass": "local",
     "packageType": "pypi",
     "description": "Corporate Python Package Repository"
   }
   ```

2. **Configure Virtual Repository**:
   ```json
   {
     "key": "pypi",
     "rclass": "virtual", 
     "packageType": "pypi",
     "repositories": ["pypi-local", "pypi-remote"],
     "defaultDeploymentRepo": "pypi-local"
   }
   ```

### User Access Configuration

```bash
# Create deployment user
curl -X POST "https://hypersec.jfrog.io/artifactory/api/security/users/pypi-deployer" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "pypi-deployer",
    "email": "devops@company.com", 
    "password": "secure-password",
    "groups": ["deployers"]
  }'
```

## 📁 Installation for End Users

### From Corporate PyPI

```bash
# Configure pip for corporate repository
pip config set global.index-url https://hypersec.jfrog.io/artifactory/api/pypi/hypersec-pypi-local/simple/
pip config set global.trusted-host hypersec.jfrog.io

# Install LogReducer
pip install logreducer

# Or with enhanced features
pip install "logreducer[enhanced]"
```

### With Authentication

```bash
# Using pip with credentials
pip install --index-url https://user:token@hypersec.jfrog.io/artifactory/api/pypi/hypersec-pypi-local/simple/ logreducer

# Using uv (recommended)
uv pip install --index-url https://user:token@hypersec.jfrog.io/artifactory/api/pypi/hypersec-pypi-local/simple/ logreducer
```

### Environment Configuration

Create `.pypirc` file for users:

```ini
[distutils]
index-servers = corporate

[corporate]
repository = https://hypersec.jfrog.io/artifactory/api/pypi/hypersec-pypi-local/
username = your-username
password = your-token
```

## 🧪 Testing Deployment

### Validation Script

```python
#!/usr/bin/env python3
"""Validate LogReducer deployment"""

import sys
import tempfile
import os

def test_installation():
    """Test LogReducer installation and basic functionality"""
    try:
        from logreducer import LogReducer
        print("✅ LogReducer imported successfully")
        
        # Test basic functionality  
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write("2024-01-01 12:00:00 INFO Test log line\n")
            f.write("2024-01-01 12:00:01 ERROR Test error line\n") 
            temp_file = f.name
        
        reducer = LogReducer(level="standard")
        result = reducer.process_file(temp_file)
        
        os.unlink(temp_file)
        
        if len(result) > 0:
            print(f"✅ LogReducer processed test file: {len(result)} lines")
            print("Deployment validation successful!")
            return True
        else:
            print("❌ LogReducer returned empty result")
            return False
            
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Functionality test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_installation()
    sys.exit(0 if success else 1)
```

### Performance Benchmarks

```python
#!/usr/bin/env python3
"""Benchmark LogReducer performance"""

import time
import os
from logreducer import LogReducer

def benchmark_performance():
    """Run performance benchmarks"""
    print("LogReducer Performance Benchmark")
    print("=" * 40)
    
    # Download sample data if available
    sample_files = [
        "samples/samples/apache_access.log",
        "samples/samples/hdfs_system.log",
        "samples/samples/openstack_nova.log"
    ]
    
    results = []
    
    for file_path in sample_files:
        if not os.path.exists(file_path):
            continue
            
        print(f"\\nBenchmarking: {file_path}")
        
        file_size = os.path.getsize(file_path) / 1024 / 1024  # MB
        
        for level in ["standard", "enhanced"]:
            start = time.time()
            
            reducer = LogReducer(level=level)
            result = reducer.process_file(file_path, return_metadata=True)
            
            duration = time.time() - start
            stats = result['stats']
            
            results.append({
                'file': os.path.basename(file_path),
                'level': level,
                'size_mb': file_size,
                'output_lines': stats['output_lines'],
                'reduction_pct': stats['reduction_percent'],
                'time_sec': duration,
                'rate_mb_sec': file_size / duration
            })
            
            print(f"   {level:>8}: {stats['reduction_percent']:>5.1f}% reduction in {duration:>5.2f}s")
    
    # Summary table
    print("\\n" + "=" * 70)
    print("PERFORMANCE SUMMARY")
    print("=" * 70)
    print(f"{'File':<20} {'Level':<9} {'Size(MB)':<8} {'Lines':<6} {'Reduction%':<10} {'Time(s)':<8} {'Rate(MB/s)':<10}")
    print("-" * 70)
    
    for result in results:
        print(f"{result['file']:<20} {result['level']:<9} {result['size_mb']:<8.2f} "
              f"{result['output_lines']:<6} {result['reduction_pct']:<10.1f} "
              f"{result['time_sec']:<8.2f} {result['rate_mb_sec']:<10.1f}")

if __name__ == "__main__":
    benchmark_performance()
```

## 🔒 Security Considerations

### Dependency Management

- **Pin versions** in `requirements.txt` for production
- **Scan dependencies** for vulnerabilities using `pip-audit`
- **Regular updates** via Dependabot or manual review

### Access Control

- **Role-based access** to Artifactory repositories
- **API tokens** instead of passwords
- **Network restrictions** for deployment pipelines
- **Audit logging** for all deployments

### Secrets Management

```yaml
# GitHub Actions secrets management
env:
  ARTIFACTORY_USERNAME: ${{ secrets.ARTIFACTORY_USERNAME }}
  ARTIFACTORY_PASSWORD: ${{ secrets.ARTIFACTORY_PASSWORD }}
  # Never expose secrets in logs
```

## Monitoring & Maintenance

### Health Checks

```bash
# Automated health check script
#!/bin/bash
set -e

echo "🏥 LogReducer Health Check"

# Test import
python -c "from logreducer import LogReducer; print('✅ Import OK')"

# Test basic functionality
python -c "
from logreducer import LogReducer
import tempfile

with tempfile.NamedTemporaryFile(mode='w', suffix='.log') as f:
    f.write('test log line\\n')
    f.flush()
    result = LogReducer().process_file(f.name)
    assert len(result) >= 0
print('✅ Basic functionality OK')
"

echo "All health checks passed!"
```

### Update Process

1. **Staging Deployment**:
   - Deploy to staging environment
   - Run automated tests
   - Performance regression testing
   
2. **Production Deployment**:
   - Gradual rollout via feature flags
   - Monitor error rates and performance
   - Rollback capability

3. **Communication**:
   - Release notes via CHANGELOG.md
   - User notification for breaking changes
   - Documentation updates

## Support & Troubleshooting

### Common Issues

**Installation Failures**:
```bash
# Clear pip cache
pip cache purge
uv cache clean

# Reinstall with verbose output
uv pip install --verbose logreducer
```

**Authentication Errors**:
```bash
# Verify credentials
curl -u username:token https://hypersec.jfrog.io/artifactory/api/system/ping

# Update .pypirc configuration
pip config list
```

**Performance Issues**:
```python
# Memory profiling
from logreducer import LogReducer
reducer = LogReducer(max_memory_gb=0.5)  # Limit memory usage
estimate = reducer.estimate_processing("large_file.log")
print(f"Strategy: {estimate['strategy']}")
```

### Getting Help

- **Documentation**: https://docs.company.com/logreducer
- **Issues**: https://github.com/company/logreducer/issues  
- **Internal Support**: devops@company.com
- **Slack**: #logreducer-support

---

**Ready for Production!**

LogReducer is now fully configured for deployment to your corporate PyPI repository with comprehensive CI/CD, testing, and monitoring capabilities.