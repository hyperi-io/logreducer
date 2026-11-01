# logreducer

Reduce gigabytes of logs to a small, representative sample. By default you get a couple of examples of each recurring pattern, and the repeats are dropped.

It ships as a CLI and as a Python library with an IO-agnostic core.

## What it gives you

- A `logreducer` command that reduces a file, a SQL or ClickHouse query, or a Kafka topic, straight from the shell.
- Pattern mode streams through a bounded dedup cache, fuzzy index and template store, so memory does not grow with the line count or the number of distinct lines.
- A memory budget that decides how a file is read: whole, in chunks, or reservoir-sampled once it passes five times the budget.
- Four modes: pattern (Drain3 template mining), anomaly (Isolation Forest), temporal (one example per template per time window) and hybrid.
- ERROR, FATAL and CRITICAL lines always come through, one per distinct shape and ahead of the reduced output, in every mode and however a file is read. A SQL or ClickHouse source samples in the database first, so only the lines it returns are seen.
- A core with no IO dependencies: anything re-iterable that yields `str` lines is a source, and anything with `write(lines)` is a sink.
- Seeded SQL sampling and ClickHouse `SAMPLE` for tables too big to scan in full.
- `reduce_to_target` to collect about N representative lines from a large source, holding roughly one batch in memory.
- Injection points for a host application's own config cascade and logging.

## Example

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

```text
540 -> 4
WARN slow query table=events ms=300
WARN slow query table=events ms=301
INFO GET /health 200 req=0
INFO GET /health 200 req=1
```

From the shell it is `logreducer app.log -o reduced.log`. `level` is `standard`, `enhanced` or `maximum`, trading speed for wider coverage on a 0.5, 1 or 2 GB budget.

## Extras

| Extra | Adds |
|---|---|
| `enhanced` | Fuzzy dedup with MinHash LSH, whose index holds the last `dedup_cache_size` near-unique lines, and faster hashing |
| `sql` | `SQLSource` over SQLAlchemy, with your own DBAPI driver |
| `clickhouse` | `ClickHouseSource` over clickhouse-connect |
| `kafka` | `KafkaSource` and `KafkaSink` over confluent-kafka |

Template mining is derived from [Drain3](https://github.com/logpai/Drain3), MIT licence, with its licence text in the module header.

Docs and source are at <https://github.com/hyperi-io/logreducer>. Requires Python 3.14 or later. Licensed Apache-2.0: <https://github.com/hyperi-io/logreducer/blob/main/LICENSE>.
