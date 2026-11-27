# logreducer

Reduce gigabytes of logs to a small, representative sample. By default you get a couple of examples of each recurring pattern, and the repeats are dropped.

It ships as a CLI and as a Python library with an IO-agnostic core.

## What it gives you

- A `logreducer` command that reduces a file, a SQL or ClickHouse query, or a Kafka topic, straight from the shell.
- Pattern mode streams through a bounded dedup cache, fuzzy index and template store, so memory does not grow with the line count. Line length and the spread of token counts per line still add to it.
- A memory budget that decides how a file is read: whole, in chunks, or reservoir-sampled once it passes five times the budget.
- Four modes: pattern (Drain3 template mining), anomaly (Isolation Forest), temporal (one example per template per time window) and hybrid.
- Lines naming ERROR, FATAL or CRITICAL as a whole word, in any case, come through ahead of the reduced output, one per distinct message once standalone numbers, IPs, MACs, UUIDs, hex IDs and ISO timestamps are masked, in every mode and however a file is read, up to `max_severe_shapes` messages (`max_patterns` by default). A SQL or ClickHouse source samples in the database first, so a line the sample drops is never seen.
- A core with no IO dependencies: anything re-iterable that yields `str` lines is a source, and anything with `write(lines)` is a sink.
- Seeded SQL sampling, PostgreSQL `TABLESAMPLE` and ClickHouse `SAMPLE` for large tables, and `reduce_to_target` to collect about N representative lines from a large source, holding roughly one batch in memory.
- Injection points for a host application's config cascade and logging.

Install it and reduce a list of lines:

```console
uv add logreducer
```

```python
from logreducer import LogReducer

lines = [f"INFO GET /health 200 req={i}" for i in range(500)]
lines += [f"WARN slow query table=events ms={300 + i}" for i in range(40)]

reduced = LogReducer().reduce(lines)
print(len(lines), "->", len(reduced))
for line in reduced:
    print(line)
```

```console
540 -> 4
WARN slow query table=events ms=300
WARN slow query table=events ms=301
INFO GET /health 200 req=0
INFO GET /health 200 req=1
```

From the shell it is `logreducer app.log -o reduced.log`. `level` is `standard`, `enhanced` or `maximum`, trading speed for wider coverage on a 0.5, 1 or 2 GB budget.

Extras add adapters and fuzzy dedup:

| Extra | Adds |
|---|---|
| `enhanced` | Fuzzy dedup with MinHash LSH (the index holds the last `dedup_cache_size` near-unique lines) and faster hashing |
| `sql` | `SQLSource` over SQLAlchemy, with a DBAPI driver you install |
| `clickhouse` | `ClickHouseSource` over clickhouse-connect |
| `kafka` | `KafkaSource` and `KafkaSink` over confluent-kafka |

Template mining is derived from [Drain3](https://github.com/logpai/Drain3), MIT licence, with its licence text in the module header.

Docs and source are at <https://github.com/hyperi-io/logreducer>. PyPI lists the Python floor under Meta. Licensed Apache-2.0: <https://github.com/hyperi-io/logreducer/blob/main/LICENSE>.
