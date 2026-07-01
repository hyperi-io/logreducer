#!/usr/bin/env python3
"""LogReducer command-line interface.

A single command that reduces a log source to a representative sample. The
source is one of:

* a file - ``logreducer app.log``
* a SQL or ClickHouse query - ``logreducer --dsn postgresql://... --query '...'``
* a Kafka topic - ``logreducer --dsn kafka://broker:9092 --topic logs --group g``

The DB and Kafka sources need the matching optional extra installed
(``logreducer[sql]`` / ``[clickhouse]`` / ``[kafka]``); a plain file needs
nothing. Built on typer.
"""

import json
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from typing import Any

import typer

from .core import LogReducer
from .logging_config import setup_logging
from .sources import Source


def _err(message: str) -> None:
    """Write an error line to stderr."""
    print(message, file=sys.stderr)


def _version_callback(value: bool) -> None:
    """Eager --version handler: print version and exit."""
    if value:
        try:
            ver = _pkg_version("logreducer")
        except PackageNotFoundError:
            ver = "unknown"
        print(f"logreducer version {ver}")
        raise typer.Exit(0)


def _build_dsn_source(dsn: str, query: str | None, topic: str | None, group: str | None) -> Source:
    """Dispatch a ``--dsn`` to the matching source adapter by URL scheme.

    ``clickhouse://`` -> ClickHouseSource, ``kafka://`` -> KafkaSource, and any
    other scheme (postgresql, mysql, sqlite, ...) -> SQLSource via SQLAlchemy.
    Adapter imports are lazy so a plain-file run never needs the extras.
    """
    scheme = dsn.split("://", 1)[0].lower() if "://" in dsn else ""

    if scheme == "clickhouse":
        if not query:
            raise typer.BadParameter("--query is required for a clickhouse:// source")
        from .clickhouse import ClickHouseSource

        return ClickHouseSource(dsn, query)

    if scheme == "kafka":
        if not (topic and group):
            raise typer.BadParameter("--topic and --group are required for a kafka:// source")
        from .kafka import KafkaSource

        brokers = dsn.split("://", 1)[1]
        return KafkaSource(brokers, group, topic)

    # Everything else is standard SQL reached through SQLAlchemy.
    if not query:
        raise typer.BadParameter("--query is required for a SQL --dsn source")
    from .sql import SQLSource

    return SQLSource(dsn, query)


def _reduce(
    input_file: str | None = typer.Argument(None, help="Log file to reduce (omit when using --dsn)"),
    output: str | None = typer.Option(None, "--output", "-o", help="Output file (default: stdout)"),
    output_format: str = typer.Option("line", "--format", help="Output format: line, json, jsonl"),
    pretty_json: bool = typer.Option(False, "--pretty-json", help="Pretty-print JSON output"),
    level: str = typer.Option("standard", "--level", "-l", help="Processing level: standard, enhanced, maximum"),
    mode: str = typer.Option("pattern", "--mode", "-m", help="Processing mode: pattern, anomaly, temporal, hybrid"),
    dsn: str | None = typer.Option(None, "--dsn", help="Source DSN: postgresql://, clickhouse://, kafka://, ..."),
    query: str | None = typer.Option(None, "--query", help="SQL SELECT (first column is the log line) for --dsn"),
    topic: str | None = typer.Option(None, "--topic", help="Kafka topic (with a kafka:// --dsn)"),
    group: str | None = typer.Option(None, "--group", help="Kafka consumer group (with a kafka:// --dsn)"),
    max_memory: float | None = typer.Option(None, "--max-memory", help="Maximum memory usage in GB"),
    max_patterns: int | None = typer.Option(None, "--max-patterns", help="Maximum number of patterns to extract"),
    log: bool = typer.Option(False, "--log", help="Enable processing logs"),
    log_file: str | None = typer.Option(None, "--log-file", help="Log file path"),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level: DEBUG, INFO, WARNING, ERROR"),
    estimate: bool = typer.Option(False, "--estimate", help="Estimate processing requirements and exit (file only)"),
    metadata: bool = typer.Option(False, "--metadata", help="Include detailed metadata in output"),
    stats: bool = typer.Option(False, "--stats", help="Print processing statistics to stderr"),
    version: bool = typer.Option(
        False, "--version", "-V", callback=_version_callback, is_eager=True, help="Show version and exit"
    ),
) -> None:
    """Reduce a log source to a representative sample."""
    # Build reducer config overrides, dropping unset values.
    overrides: dict[str, Any] = {
        "max_memory_gb": max_memory,
        "max_patterns": max_patterns,
        "enable_logging": log or None,
        "log_file": log_file,
        "log_level": log_level,
        "output_format": output_format,
        "pretty_json": pretty_json or None,
    }
    kwargs = {k: v for k, v in overrides.items() if v is not None}

    try:
        reducer = LogReducer(level=level, mode=mode, **kwargs)
    except ValueError as exc:
        _err(f"Error: {exc}")
        raise typer.Exit(1) from exc

    # The reducer configures only a file sink; when --log is set the CLI also
    # wants progress on the console.
    if log:
        setup_logging(enable=True, console=True, log_file=log_file, log_level=log_level)

    # --estimate is a file-only, pre-flight sizing step.
    if estimate:
        if not input_file:
            _err("Error: --estimate requires an input file")
            raise typer.Exit(1)
        _run_estimate(reducer, input_file)
        return

    try:
        if dsn:
            source = _build_dsn_source(dsn, query, topic, group)
            try:
                result = reducer.reduce(source, output_file=output, return_metadata=metadata)
            finally:
                close = getattr(source, "close", None)
                if callable(close):
                    close()
        elif input_file:
            result = reducer.process_file(input_file, output, return_metadata=metadata)
        else:
            _err("Error: provide a log file, or --dsn with --query (SQL/ClickHouse) or --topic/--group (Kafka)")
            raise typer.Exit(1)
    except (typer.Exit, typer.BadParameter):
        raise  # our control-flow exit / typer usage errors - let typer format them
    except KeyboardInterrupt:
        _err("Processing interrupted by user")
        raise typer.Exit(1) from None
    except Exception as exc:
        # File-not-found, a missing optional extra (ImportError), or an adapter
        # failure (bad DSN, connection refused, bad SQL, Kafka error) - report a
        # clean one-line error instead of dumping a Python traceback.
        _err(f"Error: {exc}")
        raise typer.Exit(1) from exc

    _emit_result(result, output, output_format, pretty_json, metadata)

    if stats:
        _print_stats(reducer.stats)


def _run_estimate(reducer: LogReducer, input_file: str) -> None:
    """Print a pre-flight processing estimate for a file.

    The estimate is the command's product, so it goes to stdout via ``print``
    (not the library logger, which is disabled unless --log is passed).
    """
    try:
        est = reducer.estimate_processing(input_file)
    except OSError as exc:
        _err(f"Error estimating processing: {exc}")
        raise typer.Exit(1) from exc

    print("Processing Estimation")
    print("=" * 50)
    print(f"File size: {est['file_size_gb']:.2f} GB")
    print(f"Estimated memory: {est['memory_required_gb']:.2f} GB")
    print(f"Processing strategy: {est['strategy']}")
    print(f"Estimated time: {est['estimated_time_seconds']:.0f} seconds")
    print(f"Will sample data: {'Yes' if est['will_sample'] else 'No'}")
    print(f"Expected output lines: ~{est['estimated_output_lines']:,}")
    if est["memory_required_gb"] > 8.0:
        _err("Warning: large memory requirements detected; consider --max-memory")


def _emit_result(
    result: list[str] | dict,
    output: str | None,
    output_format: str,
    pretty_json: bool,
    metadata: bool,
) -> None:
    """Print the reduced result to stdout when not writing to a file."""
    if output:
        return  # Already written by the reducer.

    if metadata and isinstance(result, dict):
        if output_format == "json":
            print(json.dumps(result, indent=2 if pretty_json else None))
        else:
            for line in result["lines"]:
                print(line)
    elif isinstance(result, list):
        for line in result:
            print(line)


def _print_stats(stats: dict) -> None:
    """Print a processing summary to stderr (size/rate omitted for non-files)."""
    print("\nProcessing completed:", file=sys.stderr)
    input_size_mb = stats.get("input_size_mb")
    if input_size_mb is not None:
        print(f"  Input: {stats['input_lines']:,} lines ({input_size_mb:.1f} MB)", file=sys.stderr)
    else:
        print(f"  Input: {stats['input_lines']:,} lines", file=sys.stderr)
    print(f"  Output: {stats['output_lines']:,} lines", file=sys.stderr)
    print(f"  Reduction: {stats['reduction_percent']:.1f}%", file=sys.stderr)
    print(f"  Time: {stats['processing_time_seconds']:.2f}s", file=sys.stderr)
    rate = stats.get("processing_rate_mb_per_sec")
    if rate is not None:
        print(f"  Rate: {rate:.1f} MB/sec", file=sys.stderr)


def main() -> None:
    """Console-script entry point."""
    typer.run(_reduce)


if __name__ == "__main__":
    main()
