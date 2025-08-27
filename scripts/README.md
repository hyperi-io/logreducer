# Scripts Directory Structure

## Final Consolidated Architecture

After consolidation, we have a clean, minimal script structure:

```
scripts/
├── setup           # Bootstrap script (runs standalone)
├── pdev            # Developer commands (all dev tasks)
├── ci-helper       # CI/CD utilities (GitHub Actions)
├── common.py       # Shared utilities
├── pdev.yaml       # Developer tool configuration
└── ci-helper.yaml  # CI/CD configuration
```

## Script Purposes

### 1. `setup` - Bootstrap Script
**Must remain standalone** - Creates venv and initial environment
- Creates virtual environment with uv
- Installs all dependencies
- Sets up pre-commit hooks
- Initializes git tags for semantic-release
- **Run once**: `scripts/setup`

### 2. `pdev` - Developer Swiss Army Knife
All daily development commands in one place:
- `test` - Run tests
- `format` - Format code
- `lint` - Run linters
- `security` - Security scans (integrated from security_scan.py)
- `build` - Build packages
- `clean` - Clean artifacts
- `version-check` - Verify version consistency
- `init-release` - Initialize semantic-release
- `all` - Run everything

### 3. `ci-helper` - CI/CD Utilities
Used by GitHub Actions and CI/CD pipelines:
- `update-version` - Update VERSION file only
- `verify-versions` - Check all versions match
- `prepare-release` - Pre-release checks
- `test-editable` - Test PEP 660 editable install (from test_editable_install.py)

## Removed Scripts (Now Integrated)

The following scripts were merged and removed:
- ❌ `security_scan.py` → Integrated into `pdev security`
- ❌ `test_editable_install.py` → Moved to `ci-helper test-editable`
- ❌ `version.py` → Split between `pdev version-check` and `ci-helper verify-versions`
- ❌ `init_semantic_release.py` → Integrated into `pdev init-release`
- ❌ `update_version_file.py` → Moved to `ci-helper update-version`

## Configuration Files

### `pdev.yaml`
- Tool requirements and install hints
- Development settings
- Security scan configuration
- Test and build settings

### `ci-helper.yaml`
- Version file locations and patterns
- Release configuration
- CI/CD specific settings
- Project structure detection

## Key Benefits

1. **No Overlapping Functionality** - Each command has one home
2. **Clear Separation** - Dev tools vs CI/CD tools
3. **Single Entry Points** - Just `pdev` for devs, `ci-helper` for CI
4. **Configuration-Driven** - No hardcoded paths or settings
5. **Template Ready** - Can copy to any Python project

## Usage Examples

### Developer Workflow
```bash
# One-time setup
scripts/setup

# Daily development
scripts/pdev format
scripts/pdev test
scripts/pdev security

# Before commit
scripts/pdev all
```

### CI/CD Workflow
```yaml
# In GitHub Actions
- run: python scripts/ci-helper verify-versions
- run: python scripts/ci-helper test-editable
- run: python scripts/ci-helper update-version "$VERSION"
```

## Migration Guide

If you have scripts or aliases using old commands:

| Old Command | New Command |
|-------------|-------------|
| `python scripts/security_scan.py` | `scripts/pdev security` |
| `python scripts/test_editable_install.py` | `python scripts/ci-helper test-editable` |
| `python scripts/version.py --check` | `scripts/pdev version-check` |
| `python scripts/version.py --get` | `scripts/pdev version-check` |
| `python scripts/init_semantic_release.py` | `scripts/pdev init-release` |

## Design Philosophy

- **setup** stays standalone (bootstrap requirement)
- **pdev** handles all developer-facing tasks
- **ci-helper** handles all CI/CD automation tasks
- **No duplication** - each feature lives in exactly one place
- **Configuration over code** - YAML files for customization