# LogReducer

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://python.org)
[![License: HyperSec EULA](https://img.shields.io/badge/License-HyperSec_EULA-red.svg)](https://hypersec.io/eula)
[![Package Version](https://img.shields.io/badge/version-3.2.0-green.svg)](https://pypi.org/project/logreducer/)

A high-performance Python module for intelligently reducing large log files (GB+) to representative samples while preserving critical patterns. Features memory-safe processing, temporal awareness, and anomaly detection.

## Features

- **Memory-Safe Processing**: Handle multi-GB log files with constant memory usage
- **Multiple Processing Modes**: Pattern-based, anomaly detection, temporal analysis, and hybrid approaches
- **High Performance**: Process GB+ files in seconds with optimized algorithms
- **Intelligent Sampling**: Generate representative samples preserving critical patterns
- **Temporal Awareness**: Time-based pattern extraction and burst detection
- **Anomaly Detection**: ML-powered identification of unusual log entries
- **Flexible Configuration**: Three processing levels with extensive customization options

## Installation

### From Private PyPI Repository (Corporate)

```bash
# Configure pip for your corporate Artifactory repository
pip install --index-url https://your-company.jfrog.io/artifactory/api/pypi/pypi/simple/ logreducer

# Or with enhanced features
pip install --index-url https://your-company.jfrog.io/artifactory/api/pypi/pypi/simple/ "logreducer[enhanced]"
```

### Development Installation

```bash
git clone https://github.com/hypersec-io/logreducer.git
cd logreducer
pip install -e ".[dev]"
```

## Quick Start

### Basic Usage

```python
from logreducer import LogReducer

# Simple usage - reduce a log file
reducer = LogReducer(level="standard")
reduced_logs = reducer.process_file("app.log", output_file="reduced.log")

print(f"Reduced {len(reduced_logs)} representative log lines")
```

### Advanced Configuration

```python
# Advanced usage with custom settings
reducer = LogReducer(
    level="enhanced",           # standard | enhanced | maximum
    mode="hybrid",              # pattern | anomaly | temporal | hybrid  
    max_memory_gb=4.0,          # Memory limit
    max_patterns=2000           # Maximum patterns to extract
)

# Process with metadata
result = reducer.process_file("huge.log", return_metadata=True)
print(f"Processing stats: {result['stats']}")
```

### Command Line Usage

```bash
# Basic log reduction
logreducer --input app.log --output reduced.log --level standard

# Enhanced processing with anomaly detection
logreducer --input production.log --mode anomaly --level enhanced --memory 8GB
```

## Processing Modes

| Mode | Description | Best For | Performance |
|------|-------------|----------|-------------|
| `pattern` | Drain3-based pattern extraction | Structured logs, application logs | Fastest |
| `anomaly` | ML-powered anomaly detection | Security logs, error detection | Moderate |
| `temporal` | Time-aware pattern analysis | Time-series logs, monitoring | Fast |
| `hybrid` | Combined approach | Complex logs, maximum coverage | Comprehensive |

## Processing Levels

| Level | Speed | Memory | Reduction % | Features |
|-------|-------|--------|-------------|----------|
| `standard` | Fast | Low | 99%+ | Basic deduplication + patterns |
| `enhanced` | Moderate | Medium | 99.5%+ | + Fuzzy deduplication + ML |
| `maximum` | Thorough | High | 99.9%+ | + Advanced algorithms + entropy |

## Configuration Options

### Memory Management

```python
reducer = LogReducer(
    max_memory_gb=2.0,          # Memory limit
    chunk_size=50000,           # Lines per processing chunk
    dedup_cache_size=100000     # Deduplication cache size
)
```

### Quality Control

```python
reducer = LogReducer(
    drain_similarity=0.4,       # Pattern similarity threshold
    min_pattern_occurrences=2,  # Minimum pattern frequency
    fuzzy_threshold=0.8,        # Fuzzy deduplication threshold
    anomaly_contamination=0.1   # Expected anomaly percentage
)
```

### Temporal Processing

```python
reducer = LogReducer(
    temporal_window_minutes=60,     # Time window for grouping
    preserve_burst_patterns=True    # Keep burst event patterns
)
```

## Performance Benchmarks

| File Size | Mode | Level | Processing Time | Memory Usage | Reduction % |
|-----------|------|-------|----------------|--------------|-------------|
| 100 MB | pattern | standard | 3s | 50 MB | 99.5% |
| 1 GB | pattern | standard | 30s | 200 MB | 99.8% |
| 10 GB | pattern | standard | 5m | 1 GB | 99.9% |
| 10 GB | hybrid | enhanced | 8m | 2 GB | 99.95% |

## Advanced Usage

### Programmatic Processing

```python
# Estimate processing requirements
estimate = reducer.estimate_processing("large.log")
print(f"Estimated time: {estimate['estimated_time_seconds']}s")
print(f"Strategy: {estimate['strategy']}")

# Process multiple files
files = ["app1.log", "app2.log", "app3.log"]
for file in files:
    reduced = reducer.process_file(file, output_file=f"reduced_{file}")
```

### Integration with Analysis Pipelines

```python
# Get processed logs for advanced analysis
reducer = LogReducer(mode="hybrid", level="enhanced")
result = reducer.process_file("production.log", return_metadata=True)

# Prepare for analysis
analysis_data = {
    "patterns": result['patterns'],
    "anomalies": result.get('anomalies', []),
    "sample_lines": result['lines']
}
```

### Custom Output Processing

```python
# Process and filter results
reduced_logs = reducer.process_file("app.log")

# Filter for errors only
errors = [line for line in reduced_logs if 'ERROR' in line.upper()]
print(f"Found {len(errors)} error patterns")
```

## Log Format Support

LogReducer automatically detects and handles various log formats:

- **ISO 8601**: `2024-01-01T12:00:00Z`
- **Apache/Nginx**: `[01/Jan/2024:12:00:00 +0000]`  
- **Syslog**: `Jan 01 12:00:00`
- **Application**: `2024-01-01 12:00:00.123`
- **Custom formats** via timestamp parsing

## Error Handling

```python
try:
    reducer = LogReducer(level="enhanced")
    result = reducer.process_file("app.log")
except FileNotFoundError:
    print("Log file not found")
except MemoryError:
    print("Insufficient memory - try standard level")
except Exception as e:
    print(f"Processing error: {e}")
```

## Development

### Setup Development Environment

```bash
git clone https://github.com/hypersec-io/logreducer.git
cd logreducer
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest                          # Run all tests
pytest -v tests/test_core.py   # Run specific test file
pytest -m "not slow"           # Skip slow tests
```

### Code Quality

```bash
black logreducer/              # Format code
flake8 logreducer/             # Lint code  
mypy logreducer/               # Type check
```

## Requirements

### Core Dependencies
- Python 3.8+
- drain3 >= 0.9.0
- psutil >= 5.9.0
- loguru >= 0.7.0

### Enhanced Features (Optional)
- scikit-learn >= 1.3.0 (anomaly detection)
- numpy >= 1.24.0 (numerical processing)
- xxhash >= 3.0.0 (fast hashing)
- datasketch >= 1.5.0 (fuzzy deduplication)

## License

This project is licensed under the HyperSec EULA - see the [LICENSE](LICENSE) file for details.

Copyright (c) HyperSec 2025. All rights reserved.

For complete license terms, visit: https://hypersec.io/eula

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Support

- **Documentation**: [https://docs.company.com/logreducer](https://docs.company.com/logreducer)
- **Issues**: [GitHub Issues](https://github.com/company/logreducer/issues)
- **Enterprise Support**: Contact devops@company.com

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a list of changes and version history.

---

**Built by the HyperSec Development Team**