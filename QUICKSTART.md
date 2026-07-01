# LogReducer Quickstart

Get up and running with LogReducer in minutes.

## Install

```bash
pip install logreducer
# or
uv add logreducer
```

## Command line

```bash
# Reduce a file to a smaller file
logreducer app.log -o reduced.log

# Enhanced hybrid processing, JSON output
logreducer app.log -l enhanced -m hybrid --format json -o result.json

# Estimate memory/time before running
logreducer large.log --estimate
```

## Python API

```python
from logreducer import LogReducer

reducer = LogReducer()

# Reduce a file
reduced_lines = reducer.process_file("app.log")

# Reduce with metadata (lines + stats + config)
result = reducer.process_file("app.log", "reduced.log", return_metadata=True)
print(f"Reduced from {result['stats']['input_lines']} to {result['stats']['output_lines']} lines")

# Reduce any re-iterable of str lines - no file needed
reducer.reduce(["ERROR timeout", "INFO ok", "ERROR timeout"])
```

To reduce from SQL, ClickHouse, or Kafka, see the "Sources and sinks" section of the [README](README.md).

## Processing modes

| Mode | Description | Use case |
|------|-------------|----------|
| `pattern` | Drain3 pattern extraction | General log reduction (default) |
| `anomaly` | Isolation Forest anomaly detection | Find unusual events |
| `temporal` | Time-based analysis | Time-series log analysis |
| `hybrid` | Combined approach | Best-quality reduction |

## Processing levels

| Level | Description | Speed |
|-------|-------------|-------|
| `standard` | Fast deduplication + patterns | Fast |
| `enhanced` | + fuzzy dedup + anomaly ML | Medium |
| `maximum` | + entropy scoring + wider budget | Slower |

## Development setup

```bash
git clone https://github.com/hyperi-io/logreducer.git
cd logreducer
uv sync --all-extras        # create .venv and install everything

uv run pytest -m "not integration"   # fast test suite
uv run ruff check           # lint
uv run ruff format          # format
uv run mypy src/logreducer  # type check
```

`hyperi-ci check` runs the full quality + test gate the way CI does. Integration tests (ClickHouse, Kafka) need Docker or a reachable service - see [CONTRIBUTING.md](CONTRIBUTING.md).

## Verify installation

```bash
logreducer --version
python -c "import logreducer; print(logreducer.__version__)"
```

## Need help?

- **Usage and API**: [README.md](README.md)
- **Contributing**: [CONTRIBUTING.md](CONTRIBUTING.md)
- **Issues**: [GitHub Issues](https://github.com/hyperi-io/logreducer/issues)
- **Examples**: [examples/](examples/)
