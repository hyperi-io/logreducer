# LogReducer Documentation

This directory contains comprehensive documentation for LogReducer development and deployment.

## Documentation Overview

### Development Documentation
- **[DEV.md](DEV.md)** - Complete development setup guide, testing, and daily commands
- **[BUILD_AND_CI.md](BUILD_AND_CI.md)** - Build system, CI/CD pipelines, and deployment workflows
- **[DEVELOPER_ANTIPATTERNS.md](DEVELOPER_ANTIPATTERNS.md)** - Common development mistakes and how to avoid them

### Project Management & Operations
- **[VERSIONING.md](VERSIONING.md)** - Semantic versioning strategy and release management
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Production deployment guides and best practices
- **[SECURITY.md](SECURITY.md)** - Security policies, scanning, and vulnerability management

## Project Structure

```
logreducer/
├── .github/              # GitHub Actions CI/CD workflows
├── data/
│   ├── output/          # Processed log outputs (git-ignored)
│   └── samples/         # Sample log files for testing
├── docs/                # Project documentation (this directory)
├── examples/            # Usage examples and demos
├── scripts/             # Development and utility scripts
├── src/logreducer/      # Main package source code
├── tests/               # Test suite (unit + integration)
├── QUICKSTART.md        # Quick start guide for new users
├── README.md            # Main project documentation
├── CHANGELOG.md         # Version history (automated)
└── pyproject.toml       # Python package configuration
```

### Key Directories

- **`src/logreducer/`** - Core implementation modules (cli.py, core.py, etc.)
- **`data/samples/`** - Real-world log samples from LogHub dataset
- **`scripts/`** - Development tools (`pdev`, `setup`) and automation
- **`tests/`** - Comprehensive test suite with fixtures
- **`examples/`** - Code examples and usage demonstrations

## Quick Start for Developers

1. **Setup**: Follow [DEV.md](DEV.md) for complete development environment setup
2. **Build**: See [BUILD_AND_CI.md](BUILD_AND_CI.md) for build commands and CI testing
3. **Deploy**: Use [DEPLOYMENT.md](DEPLOYMENT.md) for production deployment guidance

## Sphinx Documentation

The `index.rst` file and associated `.rst` files provide the main user-facing documentation built with Sphinx.

To build the Sphinx docs:
```bash
# Using the development scripts
scripts/pdev docs

# Or manually  
cd docs/
sphinx-build -b html . _build/html
```

## Documentation Conventions

- **Markdown (.md)**: Internal development documentation
- **reStructuredText (.rst)**: User-facing API documentation  
- **Root level files**: Keep only README.md, CHANGELOG.md, LICENSE, CLAUDE.md in project root
- **Development docs**: All other .md files belong in `/docs`