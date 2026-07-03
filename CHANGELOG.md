# Changelog

All notable changes to logreducer are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and the project adheres to
[Semantic Versioning](https://semver.org/). Entries from here on are generated
by the release tooling from Conventional Commits.

## [Unreleased] - first public release

logreducer's history before open-sourcing was internal; this entry summarises
the state of the codebase at the point it went public under Apache-2.0.

### Core
- Streaming reduction engine: exact dedup -> optional fuzzy dedup (MinHash
  LSH) -> Drain3 template mining, running as one generator pipeline in
  near-constant memory.
- Four modes: `pattern`, `anomaly` (Isolation Forest), `temporal`, `hybrid`;
  three levels: `standard`, `enhanced`, `maximum`.
- IO-agnostic core: any re-iterable stream of `str` is a `Source`; output via
  `Sink`. Built-in `FileSource`/`FileSink`.
- Memory bounds: low container-friendly defaults (0.5/1/2 GB by level),
  `max_clusters` LRU bound on the template store, opt-in `anomaly_max_rows`
  cap, and a soft/hard memory watchdog.

### Adapters (optional extras)
- `logreducer[sql]`: SQLSource - SQLAlchemy server-side-cursor streaming.
- `logreducer[clickhouse]`: ClickHouseSource - native block streaming.
- `logreducer[kafka]`: KafkaSource/KafkaSink - bounded, re-iterable,
  no-commit consumer; credential-masked reprs.

### Sampling and targeting
- Seeded, dialect-aware SQL sampling (`sample=`/`sample_seed=`), native
  `TABLESAMPLE`/`SAMPLE` via `from_table()`, and `reduce_to_target()` -
  collect N representative lines from huge sources under a memory budget.

### Embedding seams
- `LogReducer(config=...)`, `BigDialConfig.from_env(*prefixes)` (cascade),
  and `setup_logging(own_sinks=False)` so a host application's config and
  logging standards can drive logreducer with a minor code change.

### Tooling
- `logreducer` CLI (typer): files, SQL/ClickHouse DSNs, Kafka topics,
  `--sample`, `--target-rows`, `--estimate`, line/json/jsonl output.
- Test suite over real public log corpora (LogHub, Internet Traffic Archive,
  SecRepo, elastic examples - PII-cleansed) against real PostgreSQL, MySQL,
  ClickHouse and Kafka/Redpanda services.
