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


def _name() -> str:
    return f"logreducer-it-{uuid.uuid4().hex[:8]}"


def _config(bootstrap, **overrides) -> dict:
    config = {"bootstrap.servers": bootstrap} if isinstance(bootstrap, str) else dict(bootstrap)
    return {**config, **overrides}


# The consumer holds about 1 KB locally, so a paused read is far from the end of the topic.
THROTTLED = {"queued.max.messages.kbytes": 1, "max.partition.fetch.bytes": 1024}


def test_source_stops_at_the_end_offsets_it_started_with(kafka_bootstrap):
    from logreducer.kafka import KafkaSink, KafkaSource

    topic = _name()
    lines = [f"INFO first batch {i}" for i in range(2_000)]
    KafkaSink(kafka_bootstrap, topic).write(lines)
    source = KafkaSource(_config(kafka_bootstrap, **THROTTLED), group_id=_name(), topics=topic)

    consumed = []
    for line in source:
        if not consumed:
            KafkaSink(kafka_bootstrap, topic).write([f"INFO written during the read {i}" for i in range(50)])
        consumed.append(line)

    assert consumed == lines


def test_source_reads_from_the_start_whatever_its_group_committed(kafka_bootstrap):
    from confluent_kafka import Consumer, TopicPartition

    from logreducer.kafka import KafkaSink, KafkaSource

    topic, group = _name(), _name()
    lines = [f"INFO line {i}" for i in range(100)]
    KafkaSink(kafka_bootstrap, topic).write(lines)
    # Another member of the group commits half way through the topic.
    other = Consumer(_config(kafka_bootstrap, **{"group.id": group}))
    try:
        other.commit(offsets=[TopicPartition(topic, 0, 50)], asynchronous=False)
    finally:
        other.close()

    assert list(KafkaSource(kafka_bootstrap, group_id=group, topics=topic)) == lines


def test_empty_polls_before_the_end_do_not_end_the_read(kafka_bootstrap):
    from logreducer.kafka import KafkaSink, KafkaSource

    topic = _name()
    lines = [f"INFO line {i}" for i in range(2_000)]
    KafkaSink(kafka_bootstrap, topic).write(lines)
    # A 1 ms poll returns empty between most fetches.
    source = KafkaSource(_config(kafka_bootstrap, **THROTTLED), group_id=_name(), topics=topic, poll_timeout=0.001)

    assert list(source) == lines


def test_a_read_that_stalls_short_of_the_end_raises(kafka_bootstrap):
    from logreducer.kafka import KafkaConsumerError, KafkaSink, KafkaSource

    topic = _name()
    KafkaSink(kafka_bootstrap, topic).write([f"INFO line {i}" for i in range(10)])
    # The broker holds each fetch until 10 MB is ready or 20 s pass, so nothing arrives inside the idle timeout.
    stalled = _config(kafka_bootstrap, **{"fetch.min.bytes": 10_000_000, "fetch.wait.max.ms": 20_000})
    source = KafkaSource(stalled, group_id=_name(), topics=topic, idle_timeout=2.0)

    with pytest.raises(KafkaConsumerError, match="stopped short of the end"):
        list(source)


def test_sink_waits_for_queue_space_rather_than_failing(kafka_bootstrap):
    from logreducer.kafka import KafkaSink, KafkaSource

    topic = _name()
    lines = [f"INFO line {i}" for i in range(2_000)]
    # A 10-message local queue fills long before the broker acknowledges anything.
    sink = KafkaSink(_config(kafka_bootstrap, **{"queue.buffering.max.messages": 10}), topic)

    assert sink.write(lines) == 2_000
    assert sorted(KafkaSource(kafka_bootstrap, group_id=_name(), topics=topic)) == sorted(lines)


def test_sink_flushes_what_it_queued_when_a_produce_fails(kafka_bootstrap):
    from confluent_kafka import KafkaException

    from logreducer.kafka import KafkaSink

    sink = KafkaSink(kafka_bootstrap, _name())
    oversized = "x" * 2_000_000  # over librdkafka's default message.max.bytes

    with pytest.raises(KafkaException):
        sink.write([f"INFO line {i}" for i in range(5)] + [oversized])

    assert len(sink._producer) == 0
