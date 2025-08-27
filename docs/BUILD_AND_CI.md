# Build and CI/CD Documentation

## Overview

LogReducer uses a hybrid build system that supports both direct script execution and Make commands for maximum flexibility.

## Local Development

### Make Commands (Recommended)
```bash
make setup      # One-time development environment setup
make test       # Run all tests
make format     # Format code with black
make lint       # Run linting checks
make all        # Run all quality checks (test + format + lint + security)
make build      # Build distribution packages
make clean      # Clean build artifacts
```

### Direct Scripts (Alternative)
```bash
scripts/setup        # One-time setup
scripts/pdev test    # Run tests
scripts/pdev format  # Format code
scripts/pdev lint    # Run linting
scripts/pdev all     # Run all checks
scripts/pdev build   # Build packages
```

## CI/CD Pipeline

The project uses GitHub Actions with direct command execution in `ci.yml`:

- **Setup**: Python environment with uv package manager
- **Install**: Development dependencies  
- **Test**: Full test suite (unit + integration)
- **Security**: Vulnerability scanning with multiple tools
- **Build**: Distribution packages for deployment

### Key Features
- **Explicit commands**: Clear visibility of what runs in CI
- **No Make dependency**: Works on any CI runner
- **Professional logging**: RFC 3339 timestamps and structured output
- **Security integration**: Automated vulnerability scanning

## Development Scripts

All development tools are centralized in the `scripts/` directory:

- **`scripts/pdev`** - Main development command (Python-based)
- **`scripts/setup`** - One-time environment setup
- **`scripts/pdev.yaml`** - Configuration for all development tools

### Configuration Management

Development configuration is unified in `scripts/pdev.yaml`:
- Tool requirements and versions
- Timeout settings for long-running operations  
- Parallel execution settings
- Professional logging configuration

## Build Artifacts

The build process creates:
- **Source distribution** (`*.tar.gz`)
- **Wheel packages** (`*.whl`)
- **Metadata files** with build information

All artifacts are created in the `dist/` directory and are suitable for deployment to PyPI or private package repositories.