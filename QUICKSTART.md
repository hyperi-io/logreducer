# LogReducer Quickstart

Get up and running with LogReducer in minutes.

## Quick Installation

```bash
# Install from PyPI (recommended)
pip install logreducer

# Or clone and install for development
git clone https://github.com/hypersec-io/logreducer.git
cd logreducer
make setup  # Sets up dev environment
```

## Basic Usage

### Command Line
```bash
# Reduce a log file
logreducer app.log -o reduced.log

# Enhanced processing with JSON output
logreducer app.log -l enhanced -m hybrid --format json -o result.json

# Estimate processing requirements
logreducer large.log --estimate
```

### Python API
```python
from logreducer import LogReducer

# Create reducer with default settings
reducer = LogReducer()

# Process a log file
reduced_lines = reducer.process_file("app.log")

# Save to file with metadata
result = reducer.process_file("app.log", "reduced.log", return_metadata=True)
print(f"Reduced from {result['stats']['input_lines']} to {result['stats']['output_lines']} lines")
```

## Development Setup

### New Developer Setup (One Command)
```bash
# Clone the repository
git clone https://github.com/hypersec-io/logreducer.git
cd logreducer

# Set up everything (creates .venv, installs deps, runs checks)
make setup
```

### Daily Development Commands
```bash
make test      # Run all tests
make format    # Format code
make lint      # Run linting
make all       # Run all quality checks
make build     # Build packages
```

### Alternative: Direct Script Usage
```bash
scripts/setup     # One-time setup
scripts/pdev test # Run tests
scripts/pdev all  # Run all checks
```

## Processing Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `pattern` | Drain3 pattern extraction | General log reduction (default) |
| `anomaly` | ML-based anomaly detection | Find unusual events |
| `temporal` | Time-based analysis | Time-series log analysis |
| `hybrid` | Combined approach | Best quality reduction |

## Processing Levels

| Level | Description | Reduction Rate | Speed |
|-------|-------------|----------------|-------|
| `standard` | Fast processing | 70-80% | Fast |
| `enhanced` | Advanced algorithms | 80-90% | Medium |
| `maximum` | Highest quality | 90-95% | Slower |

## Project Structure

```
logreducer/
├── src/logreducer/    # Main package source
├── tests/             # Test suite
├── scripts/           # Development tools
├── docs/              # Documentation
├── data/samples/      # Sample log files
└── examples/          # Usage examples
```

## Configuration

Create `config.yaml` to customize behavior:
```yaml
log_level: INFO
processing:
  level: enhanced
  mode: hybrid
  max_memory_gb: 2.0
output:
  format: json
  include_metadata: true
```

## Performance Expectations

**Real-world benchmarks:**
- **Apache logs (2MB)**: 90% reduction in 0.8s
- **System logs (25MB)**: 92% reduction in 4.2s  
- **HDFS logs (154MB)**: 92% reduction in 18.5s
- **Spark logs (368MB)**: 91% reduction in 35.1s

## Need Help?

- **Full Documentation**: [docs/DEV.md](docs/DEV.md)
- **API Reference**: [docs/](docs/)
- **Issues**: [GitHub Issues](https://github.com/hypersec-io/logreducer/issues)
- **Examples**: [examples/](examples/)

## Verify Installation

```bash
# Test CLI
logreducer --version

# Test Python import
python -c "import logreducer; print(f'Version: {logreducer.__version__}')"

# Run development tests (if cloned)
make test
```

## Troubleshooting

### Git Hooks Error
If setup shows `[ERROR] Cowardly refusing to install hooks with core.hooksPath set`:
```bash
git config --unset-all core.hooksPath
make setup  # Re-run setup
```

### Virtual Environment Issues
```bash
# Remove corrupted venv and recreate
rm -rf .venv
make setup
```

### Tool Requirements
**Need uv package manager:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Need Python 3.12+:**
```bash
python3 --version  # Check current version
# Install via system package manager if needed
```

### Linting Warnings
The codebase has some non-critical linting warnings (line length, type stubs). These don't affect functionality:
```bash
# Run tests without linting
make test

# See all warnings
make lint
```

---

**Ready to reduce some logs?**