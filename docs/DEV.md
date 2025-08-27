# LogReducer Development Guide

## Quick Start

### Option 1: Using Make (Recommended)
```bash
# Set up development environment (first time only)
make setup

# Run tests (auto-activates .venv)
make test

# Format code
make format

# Run all quality checks  
make all
```

### Option 2: Direct Script Usage
```bash
# Set up development environment (first time only)
scripts/setup

# Run tests (auto-activates .venv)
scripts/pdev test

# Format code
scripts/pdev format

# Run all quality checks  
scripts/pdev all
```

## Daily Development Commands

### Make Commands (Recommended)
| Command | Description |
|---------|-------------|
| `make setup` | Set up development environment (one-time) |
| `make test` | Run all tests |
| `make test-unit` | Run unit tests only |
| `make test-integration` | Run integration tests only |  
| `make format` | Format code with black + isort |
| `make lint` | Run linting (flake8, mypy) |
| `make build` | Build wheel/sdist packages |
| `make clean` | Clean build artifacts |
| `make security` | Run security scan |
| `make version-check` | Check version consistency |
| `make all` | Run format + lint + test + security |

### Script Commands (Alternative)
| Command | Description |
|---------|-------------|
| `scripts/setup` | Set up development environment (one-time) |
| `scripts/pdev test` | Run all tests |
| `scripts/pdev test-unit` | Run unit tests only |
| `scripts/pdev test-integration` | Run integration tests only |  
| `scripts/pdev format` | Format code with black + isort |
| `scripts/pdev lint` | Run linting (flake8, mypy) |
| `scripts/pdev build` | Build wheel/sdist packages |
| `scripts/pdev clean` | Clean build artifacts |
| `scripts/pdev security` | Run security scan |
| `scripts/pdev version-check` | Check version consistency |
| `scripts/pdev all` | Run format + lint + test + security |

## Manual Testing

```bash
# Test the package locally
scripts/dev build
.venv/bin/pip install dist/*.whl --force-reinstall
.venv/bin/logreducer --help

# Process a sample file
.venv/bin/logreducer data/samples/apache_access.log data/output/test_output.log
```

## Script Organization

**All tools are in `/scripts` directory:**

**Developer Tools:**
- `scripts/pdev` - Daily development commands (auto-activates .venv + sets PATH)
- `scripts/setup` - One-time environment setup

**Specialized Tools:**
- `scripts/common.py` - Shared logging/configuration infrastructure  
- `scripts/security_scan.py` - Comprehensive security scanning (used by `scripts/pdev security`)
- `scripts/test_editable_install.py` - PEP 660 editable install testing (used by CI)
- `scripts/pdev.yaml` - Unified development configuration (tool requirements, timeouts, paths, etc.)

## Virtual Environment

The `scripts/pdev` command **automatically**:
- Activates `.venv` virtual environment 
- Adds `/scripts` to PATH
- Uses correct Python/tools from venv

No need to manually activate venv! Just run `scripts/pdev <command>`.

**Never install packages to system Python!** All tools are in `.venv`.

## Configuration

### Unified Development Configuration

All development tool configurations, requirements, and settings are centralized in `scripts/pdev.yaml`:

**Configuration Sections:**
- **`tools`** - Tool requirements (required, optional, environment checks, platform-specific)  
- **`config`** - Script configurations (logging, timeouts, parallel jobs, paths)
- **`commands`** - Command-specific defaults (formatting, linting, testing)

**Key Benefits:**
- Single source of truth for all development settings
- Easy to modify timeouts, parallel jobs, tool requirements
- Consistent configuration across all scripts
- Fallback to sensible defaults if YAML unavailable

**Example Customizations:**
```yaml
config:
  dev:
    parallel_jobs: 8      # Increase for faster builds
    timeout_seconds: 600  # Longer timeout for slow systems
  test:
    unit_timeout: 60      # Shorter unit test timeout
  security:
    timeout_seconds: 900  # Longer security scan timeout
```

Edit `scripts/pdev.yaml` to customize any development workflow settings.

## Known Issues & Troubleshooting

### Git Hooks Issue
If you see `[ERROR] Cowardly refusing to install hooks with core.hooksPath set`, run:
```bash
git config --unset-all core.hooksPath
make setup  # Re-run setup
```

### Linting Warnings
The codebase currently has some linting warnings (line length, type annotations). These are non-critical:
- **E501**: Line length violations (79 character limit)
- **F401**: Some unused imports in conditional blocks
- **MyPy**: Missing type stubs for external libraries

The code works correctly despite these warnings. To ignore them during development:
```bash
# Run tests without linting
make test

# Skip linting in CI (not recommended for production)
scripts/pdev test --skip-lint
```

### Common Setup Issues

**Issue**: `uv` command not found
```bash
# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Issue**: Python version too old
```bash
# Check version (need 3.12+)
python3 --version

# Install Python 3.12+ via system package manager
```

**Issue**: Virtual environment corruption
```bash
# Remove and recreate
rm -rf .venv
make setup
```