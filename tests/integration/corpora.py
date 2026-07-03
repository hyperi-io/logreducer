"""Access + load the committed real-log corpora (tests/testdata/).

Reads the gzipped, PII-cleansed slices and loads them into a SQL table or a
Kafka topic so the integration tests can reduce the SAME real data through
every Source (in-memory list, SQLSource, KafkaSource) and compare.
"""

from __future__ import annotations

import gzip
import json
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

TESTDATA_DIR = Path(__file__).resolve().parent.parent / "testdata"


def unique_name(prefix: str) -> str:
    """A collision-free table/topic name (safe on shared, persistent instances).

    Every run gets its own suffix, so parallel or repeated runs against the same
    PET ClickHouse/Kafka never clash, and teardown only drops what it created.
    """
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def manifest() -> list[dict[str, Any]]:
    """The dataset manifest (name, domain, source, licence, line count, ...)."""
    return json.loads((TESTDATA_DIR / "manifest.json").read_text())


def dataset_names() -> list[str]:
    """Names of all committed datasets, in manifest order."""
    return [entry["name"] for entry in manifest()]


def read_lines(name: str, *, limit: int | None = None) -> Iterator[str]:
    """Yield decompressed log lines for a dataset (bad bytes replaced, not raised)."""
    path = TESTDATA_DIR / f"{name}.log.gz"
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh):
            if limit is not None and i >= limit:
                return
            # Full strip + skip-blank, matching FileSource/SQLSource/ClickHouse
            # line semantics, so the same dataset reduces identically whether it
            # arrives in memory or from a store.
            stripped = line.strip()
            if stripped:
                yield stripped


def read_all(name: str, *, limit: int | None = None) -> list[str]:
    """The dataset's lines as a list (a valid in-memory Source)."""
    return list(read_lines(name, limit=limit))


def load_into_sql(engine: Any, table: str, name: str, *, limit: int | None = None) -> int:
    """Create ``table`` and stream a dataset's lines into it; return the row count.

    ``line`` is TEXT on every backend (log lines can be long). Batched inserts
    keep it quick even for tens of thousands of rows.
    """
    from sqlalchemy import text

    inserted = 0
    with engine.begin() as conn:
        conn.execute(text(f"CREATE TABLE {table} (id INTEGER, line TEXT)"))
        batch: list[dict[str, Any]] = []
        for line in read_lines(name, limit=limit):
            batch.append({"i": inserted, "l": line})
            inserted += 1
            if len(batch) >= 1000:
                conn.execute(text(f"INSERT INTO {table} (id, line) VALUES (:i, :l)"), batch)
                batch = []
        if batch:
            conn.execute(text(f"INSERT INTO {table} (id, line) VALUES (:i, :l)"), batch)
    return inserted


def drop_sql_table(engine: Any, table: str) -> None:
    """Best-effort DROP of a temp table (cleanup on shared/persistent engines)."""
    from sqlalchemy import text

    with engine.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {table}"))


def load_into_clickhouse(client: Any, table: str, name: str, *, limit: int | None = None) -> int:
    """Create a MergeTree table and stream a dataset's lines in; return the count."""
    client.command(f"CREATE TABLE {table} (id UInt64, line String) ENGINE = MergeTree ORDER BY id")
    rows: list[list[Any]] = []
    inserted = 0
    for line in read_lines(name, limit=limit):
        rows.append([inserted, line])
        inserted += 1
        if len(rows) >= 5000:
            client.insert(table, rows, column_names=["id", "line"])
            rows = []
    if rows:
        client.insert(table, rows, column_names=["id", "line"])
    return inserted


def drop_clickhouse_table(client: Any, table: str) -> None:
    """Best-effort DROP of a temp ClickHouse table."""
    client.command(f"DROP TABLE IF EXISTS {table}")


def _kafka_conf(config: str | dict[str, Any]) -> dict[str, Any]:
    """Normalise a bootstrap string or a full librdkafka config dict to a dict."""
    return dict(config) if isinstance(config, dict) else {"bootstrap.servers": config}


def load_into_kafka(config: str | dict[str, Any], topic: str, name: str, *, limit: int | None = None) -> int:
    """Produce a dataset's lines to ``topic``; return the count produced.

    ``config`` is a bootstrap string or a full librdkafka config dict (SASL/TLS
    for the authenticated PET broker).
    """
    from confluent_kafka import Producer

    conf = _kafka_conf(config)
    conf.update({"linger.ms": 50, "batch.size": 1 << 20})
    producer = Producer(conf)
    produced = 0
    for line in read_lines(name, limit=limit):
        producer.produce(topic, value=line.encode("utf-8", errors="replace"))
        produced += 1
        if produced % 10000 == 0:
            producer.poll(0)
    # flush() returns the number of messages STILL undelivered - a non-zero
    # value means silent data loss, so fail loudly rather than let the caller
    # count produce() calls as deliveries.
    undelivered = producer.flush(60)
    if undelivered:
        raise RuntimeError(f"{undelivered} of {produced} messages not delivered to {topic} within 60s")
    return produced


def delete_kafka_topic(config: str | dict[str, Any], topic: str) -> None:
    """Best-effort delete of a temp topic (cleanup on shared/persistent brokers)."""
    import contextlib

    from confluent_kafka.admin import AdminClient

    admin = AdminClient(_kafka_conf(config))
    for future in admin.delete_topics([topic]).values():
        with contextlib.suppress(Exception):
            future.result(timeout=30)
