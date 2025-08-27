# Script Architecture

## Overview

The LogReducer project uses a consolidated script architecture with two main entry points:

1. **`scripts/pdev`** - Developer commands (local development)
2. **`scripts/ci-helper`** - CI/CD utilities (GitHub Actions)

## Developer Scripts (`pdev`)

The `pdev` script is the main entry point for all development tasks.

### Usage
```bash
scripts/pdev <command>
```

### Available Commands

| Command | Description |
|---------|-------------|
| `test` | Run all tests |
| `test-unit` | Run unit tests only |
| `test-integration` | Run integration tests only |
| `format` | Format code with black + isort |
| `lint` | Run flake8 + mypy |
| `build` | Build wheel/sdist packages |
| `clean` | Clean build artifacts |
| `security` | Run security scans |
| `version-check` | Check version consistency |
| `init-release` | Initialize semantic-release (first-time setup) |
| `all` | Run format + lint + test + security |

### Features
- **Auto-activates virtual environment** - No need to manually activate
- **Adds scripts to PATH** - Helper scripts available automatically
- **Configuration-driven** - Uses `pdev.yaml` for settings
- **Logging support** - Professional logging with levels

### Example Workflow
```bash
# Initial setup
scripts/setup

# Daily development
scripts/pdev format    # Format code
scripts/pdev test      # Run tests
scripts/pdev all       # Full validation

# Release preparation
scripts/pdev version-check  # Verify versions
scripts/pdev build          # Create packages
```

## CI/CD Scripts (`ci-helper`)

The `ci-helper` script provides utilities for CI/CD pipelines.

### Usage
```bash
scripts/ci-helper <command> [options]
```

### Available Commands

| Command | Description | Usage |
|---------|-------------|-------|
| `update-version` | Update VERSION file | `ci-helper update-version 1.2.3` |
| `verify-versions` | Check version consistency | `ci-helper verify-versions` |
| `prepare-release` | Prepare for release | `ci-helper prepare-release` |

### Configuration

Configured via `scripts/ci-helper.yaml`:

```yaml
version:
  files:
    version_file: "VERSION"
    pyproject_toml: "pyproject.toml"
    init_file: "src/logreducer/__init__.py"
  patterns:
    pyproject:
      section: '^\[project\]'
      version: '^version = "(.*?)"'
```

### GitHub Actions Integration

Used in `.github/workflows/release-python.yml`:

```yaml
- name: Update VERSION file
  run: python scripts/ci-helper update-version "$NEW_VERSION"

- name: Verify versions
  run: python scripts/ci-helper verify-versions
```

## Supporting Files

### Configuration Files

| File | Purpose |
|------|---------|
| `scripts/pdev.yaml` | Development tool configuration |
| `scripts/ci-helper.yaml` | CI/CD configuration |
| `scripts/common.py` | Shared utilities |

### Setup Script

**`scripts/setup`** - One-time development environment setup:
- Creates virtual environment
- Installs dependencies
- Sets up pre-commit hooks
- Initializes semantic-release tags

## Script Philosophy

### Consolidation Benefits

1. **Single Entry Point** - Developers only need to know `pdev`
2. **Consistent Interface** - All commands follow same pattern
3. **Auto-Environment** - No manual venv activation
4. **Configuration-Driven** - YAML files for customization
5. **CI/CD Separation** - Clear boundary between dev and CI

### Design Principles

- **No Hardcoding** - All paths/patterns in config files
- **Generic & Reusable** - Can be used in other Python projects
- **Professional Output** - Proper logging, no unnecessary output
- **Error Handling** - Clear error messages and exit codes
- **Cross-Platform** - Works on Linux, macOS, Windows

## Migration from Old Scripts

### Deprecated Scripts (Removed)
- `scripts/init_semantic_release.py` → `pdev init-release`
- `scripts/update_version_file.py` → `ci-helper update-version`
- `scripts/version.py` → `pdev version-check`

### Command Mapping

| Old Command | New Command |
|-------------|-------------|
| `python scripts/version.py --get` | `pdev version-check` |
| `python scripts/init_semantic_release.py` | `pdev init-release` |
| `python scripts/security_scan.py` | `pdev security` |
| `make test` | `pdev test` |
| `make format` | `pdev format` |

## Extending the Scripts

### Adding a New Developer Command

1. Add function to `scripts/pdev`:
```python
elif command == "new-command":
    # Implementation here
```

2. Update help text in `main()` function

3. Add configuration to `pdev.yaml` if needed

### Adding a CI/CD Utility

1. Add function to `scripts/ci-helper`:
```python
def new_utility():
    # Implementation
```

2. Add subparser in `main()`

3. Update `ci-helper.yaml` for configuration

## Best Practices

1. **Always use pdev for development** - Don't bypass the scripts
2. **Check versions before release** - Run `pdev version-check`
3. **Use semantic commits** - Enable automatic versioning
4. **Run full validation** - `pdev all` before pushing
5. **Initialize tags early** - `pdev init-release` on new projects

## Template Usage

These scripts are designed to be reusable across Python projects:

1. Copy `scripts/` directory to new project
2. Update project-specific paths in YAML configs
3. Customize commands as needed
4. Run `scripts/setup` to initialize

The architecture provides a professional, consistent development experience across all Python projects.