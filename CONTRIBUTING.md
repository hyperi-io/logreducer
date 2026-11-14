# Contributing to logreducer

Thanks for your interest in improving logreducer.

## Development setup

logreducer uses [uv](https://docs.astral.sh/uv/) for dependency management.

```bash
git clone https://github.com/hyperi-io/logreducer.git
cd logreducer
uv sync --all-extras   # core + ALL extras (enhanced/sql/clickhouse/kafka) + the dev group
```

## Running the checks

There is no Makefile - the canonical local gate is the same one CI runs:

```bash
hyperi-ci check          # full local gate: lint, types, security, tests
```

Or run the tools individually:

```bash
uv run ruff format             # format
uv run ruff check --fix        # lint (autofix)
uv run mypy src/logreducer     # strict type check
uv run ty check src/logreducer # Astral type check
uv run pytest -q               # tests
uv build                       # build wheel + sdist
```

## Tests

- `tests/unit/` - fast, server-free (real SQLite, real corpora, no mocks of
  internal code). `tests/integration/` - marked `integration`, run against
  real services. `tests/testdata/` holds gzipped, PII-cleansed slices of REAL
  public log datasets (see its README for provenance and the rebuild tool).
- ClickHouse and Kafka come from scalo's shared test services (`scalo.deployment.test_support.pytest_plugin`): one container each per run, shared by every xdist worker, or the always-present server the `HYPERI_TEST_*` settings in `.env.example` name. Each test gets its own database or topics, dropped afterwards. Without Docker those tests skip locally and fail in CI.
- PostgreSQL and MySQL are throwaway testcontainers, stopped at the end of the session unless `LOGREDUCER_KEEP_CONTAINERS=1`, and skip without Docker.

## Commit messages

We use [Conventional Commits](https://www.conventionalcommits.org/). Keep the
subject to 50 characters or fewer. Common types: `fix`, `feat`, `docs`,
`refactor`, `perf`, `test`, `chore`, `ci`, `build`.

Versioning and releases are automated - do NOT hand-edit the version.
semantic-release derives the next version from the commit history, then tags,
builds and publishes. Just land well-formed commits on a feature branch and
open a pull request to `main`.

## Pull requests

1. Branch from `main` (e.g. `fix/memory-leak`, `feat/clickhouse-source`).
2. Make your change with tests; keep `hyperi-ci check` green.
3. Open a pull request to `main`.

## Code style

- Python at the `requires-python` floor, [ruff](https://docs.astral.sh/ruff/) formatted at the `line-length` in `pyproject.toml`.
- Fully typed - `mypy` runs strict; annotate new code.
- Australian English in prose; ASCII-only in comments, commit messages and docs.

## Context

Depth: [docs/architecture.md](docs/architecture.md).

### What this is

A reduction engine over an abstraction, plus a CLI on top of it. The core carries
zero IO dependencies and reduces any re-iterable stream of `str` lines, so it
never owns a connection or a loading path. It is not a log shipper, not a parser,
and not an aggregator front end -- it picks a representative subset of the lines
it is given and drops the rest.

### Where things live

| Path | Holds |
|---|---|
| `src/logreducer/core.py` | `LogReducer` -- the four modes, the multi-pass orchestration, stats, output |
| `src/logreducer/sources.py`, `sinks.py` | the two structural protocols that ARE the integration surface, plus `FileSource` and `FileSink` |
| `src/logreducer/sql.py`, `clickhouse.py`, `kafka.py` | the optional adapters, one extra each |
| `src/logreducer/patterns.py`, `anomaly.py`, `temporal.py` | Drain3 mining and fuzzy dedup, Isolation Forest, time-window grouping |
| `src/logreducer/template_mining.py` | the Drain template miner, derived from Drain3 (credited under License) |
| `src/logreducer/memory.py` | `MemoryMonitor`, `BoundedDeduplicator`, the file read strategies |
| `src/logreducer/sampling.py`, `target.py` | dialect-aware SQL sampling, and the `reduce_to_target` batch loop |
| `src/logreducer/config.py` | `BigDialConfig`, the level presets, the `from_env` cascade |
| `src/logreducer/cli.py` | the `logreducer` entry point, dispatching on the `--dsn` scheme |
| `tests/unit/`, `tests/integration/` | server-free, and `integration`-marked against real services |
| `tests/testdata/` | gzipped, PII-cleansed slices of real public log datasets, with a manifest and a rebuild tool |

### Commands that prove a change

```bash
uv sync --all-extras
hyperi-ci check        # the canonical local gate -- there is no Makefile
```

Individually: `uv run ruff format`, `uv run ruff check --fix`,
`uv run mypy src/logreducer`, `uv run ty check src/logreducer`,
`uv run pytest -q`, `uv build`. Three ways green lies:

| It looks like | It is actually |
|---|---|
| `pytest -q` covered the adapters | Nothing is deselected by default -- `addopts` is only `-ra -q --strict-markers --strict-config`, so `tests/integration/` is collected and then SKIPS when there is neither a configured endpoint nor Docker. CI sets no env vars, so CI always takes the docker path and a local run may not have |
| the tree tells you the version | It does not. The version in `pyproject.toml` and `VERSION` lags the newest tag and PyPI. semantic-release resolves the version at release time |
| coverage is at the stated floor | `min_coverage` is the gate, not the measured figure. `vulture` is set to `warn`, not fail, because a library's public API reads as unused to dead-code analysis |

### What tends to bite

| Don't | Do | Why |
|---|---|---|
| Hand `reduce()` a bare generator | Hand it something whose `__iter__` returns a FRESH iterator each call | `reduce()` counts lines in one pass then re-reads to process, and hybrid reads again. A one-shot iterator is drained by the count and leaves nothing behind, so it now raises `TypeError` rather than returning an empty result (`core.py`) |
| Assume a reused `LogReducer` starts clean | Nothing -- `_reset_components()` rebuilds them per run | The dedup seen-set, both Drain3 miners and the fuzzy LSH accumulate per line. Carried into the next run they drop every line as already-seen and return empty (`core.py`) |
| Share one deduplicator across hybrid's two passes | Rebuild it before the anomaly pass | The pattern pass consumes the seen-set, so the anomaly pass sees everything as seen and no anomalies survive. Hybrid silently degrades to pattern-only (`core.py`) |
| Assume an unknown config keyword is ignored | Read the `ValueError` and fix the name | A silently dropped override means a user's tuning quietly does nothing (`core.py`) |
| Assume every template is the final Drain3 one | Allow for a cluster the `max_clusters` cap evicted | `extract_patterns` re-reads each template from the live cluster once the feed ends, so a varying cluster carries its `<*>` slots and the priority boost counts them. A cluster LRU-evicted mid-feed is gone by then and keeps the template it had when first seen (`patterns.py`) |
| Hand-edit the version | Land a conventional commit and let semantic-release do it | semantic-release writes `VERSION`, the changelog and the tag from the commit type, so a hand edit is overwritten at the next release |

### Where this sits

One declared edge in `dfe-infra/suite.yaml`.

| Repo | Direction | Kind | Mechanism |
|---|---|---|---|
| dfe-engine | outbound | `python-dep` | dfe-engine declares `logreducer[enhanced]` by range in its `pyproject.toml` and imports it lazily, inside the `smart` and `anomaly` sampler modes: `LogReducer` and `logreducer.clickhouse` in `sampling/service.py`, `logreducer.kafka` in `sampling/kafka_reader.py`. A new release is checked against that range, then taken with `uv lock --upgrade-package logreducer` and the engine's tests |

`dfe-stack suite --consumer logreducer` returns an empty edge list: no repo in
that graph is something this library depends on. The runtime dependencies
(psutil, numpy, scikit-learn, typer) are packages, declared in
`pyproject.toml`, which is where they belong.

The reason dfe-engine gives for not declaring the dependency -- pin it "once it
hits public PyPI" -- has been met since 3.4.0 was published on 2026-07-03, so
expect that edge to become an ordinary pinned dependency.
