# LogReducer Development Guide

## Project Overview

LogReducer is a high-performance log processing system designed for reducing large log files while maintaining operational visibility. The system implements advanced pattern extraction, anomaly detection, and temporal analysis algorithms.

## Current Project Status (August 28, 2025)

### Completed Implementation ✓
- **Core LogReducer functionality**: Pattern extraction, anomaly detection, temporal analysis working
- **Enterprise Configuration**: HyperSec EULA licensing, professional branding throughout
- **CLI Interface**: Complete command-line interface with processing estimation
- **Output Formats**: LINE (default), JSON, JSONL with metadata support
- **Professional API Design**: Silent by default, proper logging, no print statements
- **Memory Management**: Configurable limits with enforcement testing
- **CPU Auto-detection**: Container-aware CPU core detection for threading
- **Security Scanning**: Comprehensive vulnerability detection pipeline with configurable MIN_SECURITY_LEVEL
- **CI/CD Pipeline**: GitHub Actions with fully functional semantic-release automation
- **Documentation**: Sphinx docs, VS Code workspace, comprehensive README
- **Directory Structure**: Moved to `/data/output` structure, samples organized
- **Changelog**: Automated changelog generation via semantic-release
- **Git Repository**: Initialized with semantic versioning and automated releases
- **Dependencies**: Core deps updated (numpy, scikit-learn moved to core from optional)
- **Production Ready**: Full API testing passed, deployed to JFrog Artifactory
- **Version 3.3.1**: Semantic-release automation fully working, automatic version bumps
- **Generic Python Template**: Script structure designed for reuse as Python project template
- **JFrog Deployment**: Successfully deploying packages to JFrog Artifactory PyPI repository

### Verified Working ✓  
- **API Import**: `import logreducer` successful, LogReducer instances create without errors
- **Silent Operation**: API completely silent by default, perfect for production integration
- **Processing Modes**: Pattern, anomaly, temporal, and hybrid modes all functional
- **Configuration System**: Level/mode settings, memory limits, CPU auto-detection working
- **Output Formats**: LINE, JSON, JSONL formats with metadata support
- **Statistics Collection**: Processing metrics, reduction rates, performance data available
- **Professional Logging**: No print statements, proper logging with console/file options
- **Virtual Environment**: uv-managed .venv with all dependencies resolved
- **Git Automation**: Pushes trigger semantic-release, version bumps automated
- **Text Cleanup**: All unprofessional emojis removed, professional presentation maintained

## Architecture Principles

### Core Design
- Memory-safe streaming for unbounded file sizes
- Adaptive processing based on file characteristics  
- Configurable quality levels (Standard, Enhanced, Maximum)
- Multiple processing modes (Pattern, Anomaly, Temporal, Hybrid)

### Performance Targets
- Process 1GB logs in <30 seconds
- Achieve 90%+ reduction while preserving critical events
- Support concurrent processing of multiple files
- Memory usage capped at 500MB for streaming mode

## Development Guidelines

### Script Architecture
- **ALWAYS check `pdev` or `ci-helper` before creating new scripts**
- Developer commands belong in `scripts/pdev`
- CI/CD utilities belong in `scripts/ci-helper`
- Common functions go in `scripts/common.py`
- Only create standalone scripts for bootstrap operations (like setup)
- Consolidation prevents duplication and maintains consistency

### File System Usage
- **ALWAYS use `./.tmp` directory for temporary files and automation work**
- Never use `/tmp`, `~/tmp`, or system temporary directories for project automation
- All temporary processing, test outputs, development artifacts, and script work goes in `./.tmp`
- The `./.tmp` directory is git-ignored and project-local
- **Important:** This is for automation tooling only - the actual LogReducer application uses its own configured temp paths

### Code Style
- Follow PEP 8 with 88-character line length (Black formatter)
- Type hints for all public functions
- Comprehensive docstrings for modules and classes
- Unit tests for all new functionality

### Testing Strategy
- Unit tests: Individual component validation
- Integration tests: End-to-end workflows with real data
- Performance tests: Benchmark against sample datasets
- Coverage target: Maintain >90% test coverage

### Key Algorithms

#### Pattern Extraction (Drain3)
- Similarity threshold: 0.4-0.9 (configurable)
- Depth: 4 levels for parse tree
- Min occurrences: 2+ for pattern recognition
- Priority scoring based on error keywords and complexity

#### Anomaly Detection
- Isolation Forest with contamination rate 0.1
- TF-IDF vectorization for feature extraction
- Fallback to statistical methods when ML unavailable
- Adaptive thresholds based on data distribution

#### Temporal Analysis
- Time window: 60 minutes default (configurable)
- Pattern clustering by time buckets
- Hour-of-day and day-of-week analysis
- Event burst detection

## Configuration

### BigDial Framework
The configuration system uses a centralized BigDialConfig class:
- Environment variable overrides
- YAML configuration support
- Runtime parameter adjustment
- Validation and bounds checking

### Processing Levels
1. **Standard**: Basic pattern extraction, 70%+ reduction
2. **Enhanced**: Add anomaly detection, 80%+ reduction  
3. **Maximum**: Full analysis suite, 90%+ reduction

## Deployment

### Package Structure
```
src/logreducer/       # Source code
data/samples/         # Test datasets
tests/               # Test suite
scripts/             # Utility scripts
```

### Release Process
1. Semantic versioning (MAJOR.MINOR.PATCH)
2. Conventional commits for automated versioning
3. GitHub Actions CI/CD pipeline
4. JFrog Artifactory for private PyPI

### Dependencies
Core:
- drain3: Pattern extraction engine
- loguru: Structured logging
- tqdm: Progress visualization
- psutil: Memory monitoring
- numpy: Numerical operations (moved from optional)
- scikit-learn: Machine learning (moved from optional)

Optional (Enhanced):
- scipy: Advanced numerical operations
- polars: High-performance DataFrames
- datasketch: MinHash deduplication
- xxhash: Fast hashing algorithms

## Performance Optimization

### Memory Management
- Streaming processing for large files
- Batch sizes: 1000-10000 lines (adaptive)
- Memory monitoring with automatic throttling
- Efficient hash algorithms (xxhash when available)

### Caching Strategy
- LRU cache for pattern matching
- Memoization of expensive computations
- Persistent cache between runs (optional)

### Parallelization
- Multiprocessing for independent files
- Async I/O for cloud storage
- Thread pools for pattern matching

## Sample Datasets

The project includes 10 real-world log formats from LogHub:
- Apache, HDFS, Linux system logs
- OpenStack, Spark, Zookeeper logs
- HPC clusters (Thunderbird, BGL)
- Android, network proxy logs

## Troubleshooting

### Common Issues
1. **OOM on large files**: Reduce batch_size in config
2. **Slow processing**: Check if enhanced features disabled
3. **Low reduction**: Adjust min_pattern_occurrences
4. **Missing patterns**: Lower drain_similarity threshold

### Debug Mode
Set environment: `LOGREDUCER_DEBUG=1`
Enables verbose logging and performance profiling.

## Changelog Management

**IMPORTANT**: The changelog is now locked and should NOT be manually edited by anyone, including Claude.

- The current CHANGELOG.md reflects the complete development history up to August 25, 2025
- All future changelog updates must be handled exclusively by semantic-release automation
- This includes version bumps, release notes, and changelog entries
- Manual changelog edits are prohibited to maintain consistency with semantic versioning
- Use conventional commit messages for semantic-release to work properly

## Python Project Template Components

This project structure is designed to be reusable as a **generic Python project template**. The following components can be extracted and reused:

### ✅ **Generic Template Structure**
- **`Makefile`** - Industry standard interface calling Python scripts
- **`scripts/pdev`** - Generic Python development commands (replaces project-specific names)
- **`scripts/setup`** - Environment setup with tool requirements checking
- **`scripts/common.py`** - Centralized logging & configuration utilities
- **`scripts/security_scan.py`** - Comprehensive security scanning
- **`scripts/test_editable_install.py`** - PEP 660 editable install testing

### ✅ **Professional Logging System**
- **Tee Approach**: Scripts log to both console AND file by default  
- **Module Approach**: Only logs to file if path provided, console if specified
- **RFC 3339 Timestamps**: `2025-08-27T15:55:44.389+10:00` format
- **Enterprise Configuration**: ConfigMap → ENV vars → CLI args precedence
- **Dynaconf Integration**: YAML + environment variable + CLI argument precedence

### ✅ **CI/CD Pipeline Template**
- **Multi-stage workflow**: test → security → build → release → deploy
- **Python version detection**: Dynamic from `.python-version-config.yaml`
- **Security integration**: Uses unified security scan script
- **Semantic release**: Automated versioning and changelog
- **Professional output**: No emojis, clear status indicators

### ✅ **Hybrid Development Workflow**
**Industry Standard Make + Professional Python Scripts:**
```bash
# One-time setup
make setup

# Daily development (Make - Industry Standard)
make test               # Run all tests
make format             # Format code
make lint              # Run linting
make security          # Security scan
make all               # Run everything

# Alternative: Direct script usage
scripts/setup           # Environment setup
scripts/pdev test       # Python script with professional logging
```

**Best of Both Worlds:**
- **Make**: Industry standard, simple commands, parallel execution
- **Python Scripts**: Professional logging, configuration management, cross-platform
- **Template Ready**: Both Makefile and scripts/ can be reused across projects

### ✅ **Configuration Management**
- **`common.py`**: Centralized config utilities with enterprise patterns
- **`config.yaml`**: Auto-generated default configuration  
- **Environment Variables**: `APP_` prefix with override precedence
- **CLI Arguments**: Final override precedence
- **Kubernetes Ready**: ConfigMap/Secret mounting patterns

### ✅ **Template Extraction Guidelines**
When creating the generic template:
1. **Replace project-specific references** in help text and comments
2. **Keep `scripts/pdev`** name for consistency across all Python projects  
3. **Update `pyproject.toml`** with template project structure
4. **Preserve logging/config patterns** - they work for any Python project
5. **Keep professional emoji-free output** - suitable for enterprise use
6. **Maintain tool requirement checking** - ensures consistent dev environments

### ✅ **Template Benefits**
- **Consistent Development**: Same commands across all Python projects
- **Enterprise Ready**: Professional logging, configuration, CI/CD  
- **Security Built-in**: Comprehensive scanning from day one
- **Auto-Environment**: No manual venv activation needed
- **Scale Ready**: Supports development to production deployment

## Future Enhancements

### High Priority
- **Metrics Integration**: Metrics functionality has been moved to a separate module for better separation of concerns

### Medium Priority
- Real-time streaming mode
- Distributed processing support
- Custom pattern libraries
- Web-based visualization dashboard
- Integration with log management systems

## Testing Commands

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest --cov=logreducer --cov-report=html

# Run specific test suite
pytest tests/unit/
pytest tests/integration/

# Performance benchmarks
python scripts/benchmark.py
```

## Development Setup

### Quick Environment Check
```bash
# Check if all required development tools are installed
python scripts/check_dev_tools.py

# Show installation guide for missing tools
python scripts/check_dev_tools.py --install

# Show dfe-fedora-desktop VM setup information
python scripts/check_dev_tools.py --vm-info
```

### Manual Setup
```bash
# Create virtual environment with uv (REQUIRED)
uv venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# Install development dependencies
uv pip install -e ".[dev,enhanced]"

# Initialize Git LFS and commit hooks
git lfs install
npm install && npx husky install

# Run code formatters
black src/ tests/
isort src/ tests/

# Type checking
mypy src/logreducer/

# Security scanning (automated in CI)
python scripts/security_scan.py

# Test API functionality
python -c "import logreducer; print('Version:', logreducer.__version__)"
```

### Required Development Tools
The development environment requires:
- **Python 3.12+**: Core language and interpreter
- **uv**: Fast Python package installer and resolver
- **Git 2.34+**: Version control with Git LFS support
- **Node.js 18+**: For Husky commit hooks
- **GitHub CLI**: Repository management and automation

Run `python scripts/check_dev_tools.py` to verify all tools are installed and properly configured.

## Important Notes for Future Sessions

### Virtual Environment Management
- **ALWAYS use uv**: `uv venv .venv` and `uv pip install` for dependency management
- The project requires numpy and scikit-learn as core dependencies (not optional)
- If .venv is corrupted, remove it completely and recreate with uv

### Git Workflow
- Repository is at: https://github.com/hypersec-io/logreducer
- Uses semantic-release for automated versioning and changelog updates  
- All commits should use conventional commit format for proper automation
- Push changes to trigger CI/CD pipeline and version bumps

#### Semantic Release Commit Types
The project uses standard conventional commit types for automated version bumping:

**Version Bumping:**
- `feat:` - New features (triggers **minor** version bump)
- `fix:` - Bug fixes (triggers **patch** version bump)
- `perf:` - Performance improvements (triggers **patch** version bump)
- `refactor:` - Code refactoring (triggers **patch** version bump)

**Non-versioning (allowed but no version bump):**
- `docs:` - Documentation changes
- `style:` - Code style/formatting changes  
- `test:` - Test additions/modifications
- `chore:` - Maintenance tasks
- `ci:` - CI/CD configuration changes
- `build:` - Build system changes

**Breaking Changes:**
- Any commit with `BREAKING CHANGE:` in the footer triggers **major** version bump
- Use `!` after type for breaking changes: `feat!:` or `fix!:`

**Examples:**
- `feat: add anomaly detection mode` → 3.2.0 → 3.3.0
- `fix: resolve memory leak in pattern extractor` → 3.2.0 → 3.2.1  
- `refactor: consolidate scripts architecture` → 3.2.0 → 3.2.1
- `docs: update API documentation` → No version bump

### Key Configuration
- Logging is OFF by default (`enable_logging: bool = False`)
- Output directory is `/data/output` (moved from `/output`)
- CPU detection is container-aware for proper threading
- Memory limits are enforced and tested
- All text has been cleaned of unprofessional emojis
- Current version: 3.2.1
- Scripts consolidated: `pdev` for dev, `ci-helper` for CI/CD, `setup` for bootstrap
- Common functions in `scripts/common.py`
- Python floor version: 3.11 (this project uses 3.12 via .python-version)

### Known Issues
- None currently - all core features are working properly