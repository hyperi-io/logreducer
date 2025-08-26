# LogReducer Development Guide

## Project Overview

LogReducer is a high-performance log processing system designed for reducing large log files while maintaining operational visibility. The system implements advanced pattern extraction, anomaly detection, and temporal analysis algorithms.

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

### File System Usage
- **ALWAYS use `./.tmp` directory for temporary files and Claude Code work**
- Never use `/tmp` or system temporary directories
- All temporary processing, test outputs, and development artifacts go in `./.tmp`
- The `./.tmp` directory is git-ignored and project-local

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

Optional (Enhanced):
- scikit-learn: Machine learning
- numpy/scipy: Numerical operations
- polars: High-performance DataFrames
- datasketch: MinHash deduplication

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

## Future Enhancements

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

```bash
# Install development dependencies
pip install -e ".[dev,enhanced]"

# Setup pre-commit hooks
pre-commit install

# Run code formatters
black src/ tests/
isort src/ tests/

# Type checking
mypy src/logreducer/
```