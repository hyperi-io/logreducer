# LogReducer

[![PyPI](https://img.shields.io/pypi/v/logreducer?logo=pypi)](https://pypi.org/project/logreducer/)
[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)

Reduce gigabytes of logs to a small, representative sample - keeping the patterns and anomalies that matter and dropping the repetition that does not. Memory-safe streaming, temporal awareness, and ML-based anomaly detection.

**LogReducer is two tools in one package:**

- **A CLI you can use right now.** `logreducer app.log` reduces a file - or a SQL, ClickHouse, or Kafka source - straight from the shell. No code to write.
- **A library with an IO-agnostic core.** The engine has zero IO dependencies and reduces any re-iterable stream of `str` lines (a `Source`). Embed it in your own pipeline and feed it a file, a `list[str]`, a database cursor, or a Kafka topic; the engine never manages the connection.

## Features

- **Memory-safe streaming**: constant memory on multi-GB inputs via server-side cursors and reservoir sampling
- **Four reduction modes**: pattern (Drain3), anomaly (Isolation Forest), temporal, and hybrid
- **IO-agnostic core**: reduce a file, a `list[str]`, a database cursor, or a Kafka stream through one `Source` seam
- **Optional adapters**: SQL (SQLAlchemy), ClickHouse (clickhouse-connect), Kafka (confluent-kafka) - install only what you use
- **Three quality levels**: `standard`, `enhanced`, `maximum`
- **Structured logging**: RFC 3339 timestamps, human-readable or one-JSON-object-per-line output

## Installation

### As a CLI tool

Install it as an isolated tool so its dependencies never clash with your other Python projects. This puts a `logreducer` command on your PATH:

```bash
uv tool install logreducer     # recommended (uv)
# or
pipx install logreducer        # recommended (pipx)
```

To bundle an adapter extra with the tool:

```bash
uv tool install "logreducer[clickhouse]"
pipx install "logreducer[kafka]"
```

### As a library

Add it to your project like any other dependency:

```bash
uv add logreducer
# or
pip install logreducer
```

Optional extras (install only what you need):

```bash
uv add "logreducer[enhanced]"    # fuzzy dedup, entropy scoring, faster hashing
uv add "logreducer[sql]"         # SQLSource (SQLAlchemy) - bring your own DBAPI driver
uv add "logreducer[clickhouse]"  # ClickHouseSource (clickhouse-connect)
uv add "logreducer[kafka]"       # KafkaSource / KafkaSink (confluent-kafka)
```

> The `logreducer` command comes from a standard console-script entry point, so it works under any install: a project venv, `pip install --user` (into `~/.local/bin`), an isolated `pipx` / `uv tool` install, or a system-wide install. `pipx` / `uv tool` is the recommendation for end users - isolation without a manual venv. `pip install --user` gives a per-user install; a system-wide `sudo pip install` is possible but discouraged (it mixes into the system Python).

## Quick Start

### Library

```python
from logreducer import LogReducer

reducer = LogReducer(level="standard")

# Reduce a file (writes reduced.log + reduced.meta.json)
reduced = reducer.process_file("app.log", output_file="reduced.log")
print(f"{len(reduced)} representative lines")

# Reduce any re-iterable of lines - no file needed
lines = ["ERROR timeout upstream=payments", "INFO ok", "ERROR timeout upstream=payments"]
reduced = reducer.reduce(lines)
```

`reduce()` returns the reduced lines in memory. Pass `return_metadata=True` for a dict of `{"lines", "stats", "config"}`.

### Command line

```bash
# Reduce a file to stdout, or to a file with -o
logreducer app.log
logreducer app.log -o reduced.log -l enhanced -m hybrid

# JSON output, with run stats on stderr
logreducer app.log --format json -o result.json --stats

# Cap memory, estimate first
logreducer huge.log --max-memory 4 --estimate
```

### Reducing from a database or Kafka

The CLI dispatches on the `--dsn` scheme; a library caller constructs the source directly.

```bash
# PostgreSQL / MySQL / SQLite via SQLAlchemy (needs logreducer[sql] + a driver)
logreducer --dsn postgresql://user@host/db --query "SELECT message FROM logs"

# ClickHouse via the native driver (needs logreducer[clickhouse])
logreducer --dsn clickhouse://user@host:8123/db --query "SELECT message FROM logs"

# Kafka topic (needs logreducer[kafka])
logreducer --dsn kafka://broker:9092 --topic app-logs --group logreducer
```

```python
from logreducer import LogReducer
from logreducer.clickhouse import ClickHouseSource

reducer = LogReducer(level="enhanced", mode="hybrid")
with ClickHouseSource("clickhouse://user@host:8123/db", "SELECT message FROM logs") as source:
    reduced = reducer.reduce(source)
```

The query selects the log line as its **first column**. Sources are re-iterable (the engine makes multiple passes), so a database source re-runs its query per pass and a Kafka source re-reads from the earliest offset without committing.

## Sources and sinks

An application can hand the reducer its own IO instead of using an adapter - anything that yields `str` and can be iterated more than once is a `Source`:

```python
class MySource:
    def __iter__(self):
        yield from open_my_stream()  # must return a FRESH iterator each call

reducer.reduce(MySource())
```

Output works the same way through a `Sink` (`write(lines) -> int`). `FileSink` is built in; `KafkaSink` ships with the `kafka` extra:

```python
from logreducer import LogReducer, FileSink

reducer.reduce(source, sink=FileSink("reduced.jsonl", output_format="jsonl"))
```

## Processing modes

| Mode | Description | Best for |
|------|-------------|----------|
| `pattern` | Drain3 template mining | Structured / application logs (fastest) |
| `anomaly` | Isolation Forest outlier detection | Security and error logs |
| `temporal` | Time-aware pattern analysis | Time-series and monitoring logs |
| `hybrid` | Pattern + anomaly combined | Maximum coverage |

## Processing levels

| Level | Speed | Memory | Features |
|-------|-------|--------|----------|
| `standard` | Fast | Low | Deduplication + pattern extraction |
| `enhanced` | Moderate | Medium | + fuzzy dedup + anomaly ML |
| `maximum` | Thorough | High | + entropy scoring + wider pattern budget |

## Configuration

Override any config field as a keyword argument:

```python
reducer = LogReducer(
    level="enhanced",
    mode="hybrid",
    max_memory_gb=4.0,          # memory ceiling
    chunk_size=50000,           # lines per processing chunk
    dedup_cache_size=100000,    # bounded dedup cache
    drain_similarity=0.4,       # pattern similarity threshold
    fuzzy_threshold=0.8,        # fuzzy-dedup threshold (enhanced/maximum)
    anomaly_contamination=0.1,  # expected anomaly fraction
    temporal_window_minutes=60, # grouping window for temporal mode
    max_patterns=2000,          # cap on extracted patterns
)
```

## Logging

Logging is off by default. Enable it and pick a format via env vars:

```bash
LOG_LEVEL=DEBUG LOG_FORMAT=json logreducer app.log --log
```

`LOG_FORMAT=json` emits one JSON object per line for log aggregators; the default is human-readable (coloured in a terminal, plain in CI/containers).

## Requirements

- Python 3.12+
- Runtime: `drain3`, `numpy`, `scikit-learn`, `psutil`, `loguru`, `typer`
- `enhanced` extra: `xxhash`, `scipy`, `datasketch`
- Adapter extras: `sqlalchemy` (sql), `clickhouse-connect` (clickhouse), `confluent-kafka` (kafka)

## Development

```bash
git clone https://github.com/hyperi-io/logreducer.git
cd logreducer
uv sync --all-extras        # create .venv and install everything

uv run pytest -m "not integration"   # fast suite (integration needs Docker/services)
uv run ruff check           # lint
uv run ruff format          # format
uv run mypy src/logreducer  # type check
```

CI runs via [hyperi-ci](https://github.com/hyperi-io/hyperi-ci) - `hyperi-ci check` runs the full quality + test gate locally. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[Apache-2.0](LICENSE). Third-party attributions are recorded in [NOTICE](NOTICE).

Copyright 2026 HYPERI PTY LIMITED.
