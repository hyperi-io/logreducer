"""Integration tests over REAL public log corpora (tests/testdata/).

Verifies the core reduction capability on varied, messy, real-world logs - and
that the SAME data reduces consistently whether it arrives as an in-memory list,
from PostgreSQL (SQLSource) or from a Redpanda/Kafka topic (KafkaSource).

Docker-gated where a store is involved; the in-memory sweep needs no services.
No mocks - real corpora, real engines/brokers via testcontainers.
"""

from __future__ import annotations

import pytest

from logreducer import LogReducer, reduce_to_target
from logreducer.sql import SQLSource
from tests.integration import corpora

pytestmark = pytest.mark.integration

ALL_DATASETS = corpora.dataset_names()
# A messy, structurally-varied subset for the heavier per-store tests.
SAMPLE_DATASETS = ["loghub_mac", "loghub_openstack", "ita_nasa_http", "elastic_nginx_json"]


@pytest.mark.parametrize("name", ALL_DATASETS)
def test_reduces_every_real_dataset(name):
    """Every real dataset reduces substantially without choking on messy lines."""
    lines = corpora.read_all(name)
    assert len(lines) > 1000, f"{name} fixture looks too small"

    reducer = LogReducer(level="standard", mode="pattern")
    reduced = reducer.reduce(lines)

    assert reduced, f"{name} reduced to nothing"
    assert all(isinstance(x, str) for x in reduced)
    # max_patterns caps output hard, so real logs collapse dramatically.
    assert reducer.stats["reduction_percent"] > 80, f"{name} only {reducer.stats['reduction_percent']:.1f}%"


@pytest.mark.parametrize("mode", ["pattern", "anomaly", "temporal", "hybrid"])
def test_all_modes_survive_messy_data(mode):
    """Every mode runs to completion on the ugliest dataset (Mac) - no crash."""
    lines = corpora.read_all("loghub_mac")
    reducer = LogReducer(level="enhanced", mode=mode)
    reduced = reducer.reduce(lines)
    assert isinstance(reduced, list)
    assert len(reduced) <= len(lines)


@pytest.mark.parametrize("name", SAMPLE_DATASETS)
def test_reduce_from_postgres_matches_memory(pg_engine, name):
    """Reducing a dataset from PostgreSQL matches reducing it in memory."""
    table = corpora.unique_name(f"logs_{name}")
    try:
        corpora.load_into_sql(pg_engine, table, name)

        in_memory = LogReducer(level="standard", mode="pattern").reduce(corpora.read_all(name))
        with SQLSource(pg_engine, f"SELECT line FROM {table} ORDER BY id") as source:
            from_sql = LogReducer(level="standard", mode="pattern").reduce(source)

        # Same lines in the same order through the Source seam -> identical result.
        assert from_sql == in_memory
    finally:
        corpora.drop_sql_table(pg_engine, table)


def test_reduce_from_clickhouse(clickhouse_client):
    """A dataset loaded into ClickHouse reduces via ClickHouseSource."""
    from logreducer.clickhouse import ClickHouseSource

    name = "loghub_openstack"
    table = corpora.unique_name("logs_ch")
    try:
        loaded = corpora.load_into_clickhouse(clickhouse_client, table, name)
        source = ClickHouseSource(clickhouse_client, f"SELECT line FROM {table} ORDER BY id")
        reduced = LogReducer(level="standard", mode="pattern").reduce(source)
        assert reduced
        assert len(reduced) < loaded  # real reduction happened
    finally:
        corpora.drop_clickhouse_table(clickhouse_client, table)


def test_reduce_from_redpanda(kafka_bootstrap):
    """A dataset produced to a Redpanda topic reduces via KafkaSource."""
    pytest.importorskip("confluent_kafka")
    from logreducer.kafka import KafkaSource

    name = "loghub_openssh"
    topic = corpora.unique_name("logreducer-real")
    group = corpora.unique_name("logreducer-grp")
    try:
        produced = corpora.load_into_kafka(kafka_bootstrap, topic, name, limit=20000)
        assert produced == 20000

        source = KafkaSource(kafka_bootstrap, group_id=group, topics=topic, max_messages=20000)
        reduced = LogReducer(level="standard", mode="pattern").reduce(source)
        assert reduced
        assert len(reduced) < produced  # real reduction happened
    finally:
        corpora.delete_kafka_topic(kafka_bootstrap, topic)


def test_reduce_to_target_over_real_postgres(pg_engine):
    """reduce_to_target collects representatives from a real dataset in PostgreSQL."""
    table = corpora.unique_name("logs_target")
    try:
        corpora.load_into_sql(pg_engine, table, "loghub_openstack")

        reducer = LogReducer(level="standard", mode="pattern")
        source = SQLSource(pg_engine, f"SELECT line FROM {table}")
        outcome = reduce_to_target(source, reducer, target_rows=50, max_fetches=20)
        assert outcome["stats"]["collected"] > 0
    finally:
        corpora.drop_sql_table(pg_engine, table)
