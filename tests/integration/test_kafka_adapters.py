"""Integration test: KafkaSource + KafkaSink round-trip against a real broker.

Runs against a local broker when KAFKA_BOOTSTRAP_SERVERS is set, otherwise a
throwaway docker Kafka that is stopped as soon as the session ends. Marked
`integration` so the default suite skips it.

Each run uses a unique topic and consumer group, so it is safe against a shared
broker and leaves no durable state behind.
"""

import uuid

import pytest

from logreducer import LogReducer

pytestmark = pytest.mark.integration


def test_kafka_sink_then_source_roundtrip(kafka_bootstrap):
    from logreducer.kafka import KafkaSink, KafkaSource

    topic = f"logreducer-it-{uuid.uuid4().hex[:8]}"
    lines = [f"ERROR request failed shard={i % 3}" for i in range(30)]

    # Produce with the sink.
    produced = KafkaSink(kafka_bootstrap, topic).write(lines)
    assert produced == 30

    # Consume with the source (bounded read; stops at partition EOF).
    source = KafkaSource(
        kafka_bootstrap,
        group_id=f"logreducer-it-{uuid.uuid4().hex[:8]}",
        topics=topic,
        idle_polls=10,
    )
    consumed = list(source)
    assert len(consumed) == 30
    assert set(consumed) == set(lines)

    # Re-iterable (no offset commit -> re-reads from earliest), so the reducer's
    # multi-pass counting works over a Kafka source.
    reducer = LogReducer(level="standard", mode="pattern")
    result = reducer.reduce(source)
    assert 0 < len(result) < 30
    assert reducer.stats["input_lines"] == 30
