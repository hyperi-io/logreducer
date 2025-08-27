# Semantic Release Setup Guide

## The Chicken-and-Egg Problem

When setting up semantic-release for the first time, you need an initial git tag for semantic-release to use as a baseline. Without this tag, semantic-release doesn't know what the current version is.

## Solution: Initial Setup

### Step 1: Create Initial Tag (One-time only)

```bash
# Ensure all version files match your desired starting version
python scripts/version.py --check

# Create the initial tag
git tag -a v3.2.1 -m "Initial version tag for semantic-release baseline"

# Push the tag to GitHub
git push origin v3.2.1
```

### Step 2: Verify Setup

```bash
# Install semantic-release locally (optional, for testing)
pip install python-semantic-release

# Test that semantic-release recognizes the version
semantic-release version --print --no-push
# Should output: "3.2.1" and "No release will be made, 3.2.1 has already been released!"
```

## After Initial Setup

Once the initial tag exists, the workflow is automatic:

1. **Developer makes commits** using conventional commit format:
   - `feat:` for new features (minor version bump)
   - `fix:` for bug fixes (patch version bump)
   - `BREAKING CHANGE:` for breaking changes (major version bump)

2. **On push to main**, GitHub Actions runs semantic-release:
   - Analyzes commits since last tag
   - Determines version bump needed
   - Updates `pyproject.toml` and `__init__.py`
   - Creates new git tag
   - Updates VERSION file (via CI/CD script)
   - Creates GitHub release
   - Optionally publishes to PyPI/Artifactory

## Version File Responsibilities

| File | Managed By | Purpose |
|------|------------|---------|
| `pyproject.toml` | semantic-release | Package metadata, master version |
| `src/logreducer/__init__.py` | semantic-release | Python package version |
| `VERSION` | CI/CD workflow | Simple version reference |
| `.python-version` | Manual | Python interpreter requirement (3.12) |

## Local Development

### Reading Version
```bash
# Get current version
python scripts/version.py
# or
python scripts/version.py --get

# Check all versions match
python scripts/version.py --check
```

### Testing Semantic Release Locally

```bash
# See what version would be released (dry run)
semantic-release version --print --no-push

# Check changelog that would be generated
semantic-release changelog --unreleased
```

## CI/CD Workflow

The `.github/workflows/release-python.yml` workflow:

1. Runs on push to main branch
2. Semantic-release updates `pyproject.toml` and `__init__.py`
3. CI/CD updates `VERSION` file with: `echo "$NEW_VERSION" > VERSION`
4. Builds Python package
5. Creates GitHub release with artifacts
6. Optionally deploys to PyPI/Artifactory

## Troubleshooting

### No version bump happening
- Check commit messages follow conventional format
- Ensure commits since last tag include feat/fix/etc.
- Verify tag exists: `git tag -l`

### Version mismatch
```bash
# Check all versions
python scripts/version.py --check

# If mismatch, semantic-release will fix on next release
```

### Testing without pushing
```bash
# Dry run to see what would happen
semantic-release version --no-push --no-commit --no-tag

# Check with verbose output
semantic-release -vv version --no-push
```

## Important Notes

1. **Never manually edit versions** after initial setup
2. **Always use conventional commits** for automatic versioning
3. **The VERSION file** is updated by CI/CD, not semantic-release
4. **Python version (3.12)** in `.python-version` is NOT the package version

## Example Workflow

```bash
# 1. Make changes
edit src/logreducer/core.py

# 2. Commit with conventional format
git add .
git commit -m "fix: resolve memory leak in pattern extraction"

# 3. Push to trigger release
git push origin main

# 4. CI/CD automatically:
#    - Bumps version to 3.2.2
#    - Updates all version files
#    - Creates tag v3.2.2
#    - Publishes release
```