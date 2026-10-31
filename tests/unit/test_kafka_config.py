"""Unit tests for the Kafka adapter's pure config helpers.

These need no running broker - they exercise the pure config-merge / masking
helpers, plus the never-assigned backstop (which deliberately points at a dead
address), so they run in the normal (non-integration) suite.
"""

import pytest

from logreducer.kafka import (
    CONSUMER_DEFAULTS,
    PRODUCER_DEFAULTS,
    KafkaConsumerError,
    KafkaDeliveryError,
    KafkaSink,
    KafkaSource,
    _normalise_config,
    mask_credentials,
    merge_config,
)


def test_merge_config_user_overrides_defaults():
    merged = merge_config({"acks": "1", "bootstrap.servers": "b:9092"}, PRODUCER_DEFAULTS)
    assert merged["acks"] == "1"  # user wins over the default "all"
    assert merged["compression.type"] == "lz4"  # default preserved
    assert merged["bootstrap.servers"] == "b:9092"


def test_merge_config_disables_ssl_verify():
    merged = merge_config({}, CONSUMER_DEFAULTS, verify_ssl=False)
    assert merged["enable.ssl.certificate.verification"] == "false"


def test_consumer_defaults_never_commit_and_report_eof():
    # A logreducer source must be a bounded, repeatable read.
    assert CONSUMER_DEFAULTS["enable.auto.commit"] is False
    assert CONSUMER_DEFAULTS["enable.partition.eof"] is True
    assert CONSUMER_DEFAULTS["auto.offset.reset"] == "earliest"


def test_mask_credentials_hides_secrets():
    masked = mask_credentials({"sasl.password": "hunter2", "bootstrap.servers": "b:9092"})
    assert masked["sasl.password"] == "***"
    assert masked["bootstrap.servers"] == "b:9092"


def test_normalise_config_string_is_bootstrap():
    assert _normalise_config("host:9092") == {"bootstrap.servers": "host:9092"}


def test_normalise_config_dict_is_copied():
    original = {"bootstrap.servers": "h:9092"}
    out = _normalise_config(original)
    out["added"] = 1
    assert "added" not in original  # a copy, not an alias


def test_kafka_source_raises_when_never_assigned():
    """An unreachable broker must fail fast, not spin forever.

    Regression: empty_polls only advanced once partitions were assigned, so a
    dead broker (assignment() empty forever) left the read looping without end.
    Points at a closed local port and asserts the assignment_timeout backstop
    raises, reporting the configured value. The 1s backstop in the code under
    test is what ends the read, so there is no elapsed-time assertion.
    """
    pytest.importorskip("confluent_kafka")
    source = KafkaSource(
        "127.0.0.1:59999",  # nothing is listening here
        group_id="logreducer-test-never-assigned",
        topics="does-not-matter",
        poll_timeout=0.2,
        assignment_timeout=1.0,
    )
    with pytest.raises(KafkaConsumerError, match=r"no partition assignment within 1s"):
        list(source)


def test_kafka_sink_raises_when_nothing_is_delivered():
    """write() must not report success for messages the broker never accepted.

    Regression: no delivery callback was registered and flush()'s leftover count
    was dropped, so a dead broker still returned the number of lines produced.
    """
    pytest.importorskip("confluent_kafka")
    sink = KafkaSink(
        {"bootstrap.servers": "127.0.0.1:59999", "message.timeout.ms": 300},  # nothing is listening here
        "does-not-matter",
        flush_timeout=10,
    )
    with pytest.raises(KafkaDeliveryError) as raised:
        sink.write(["one", "two"])

    assert raised.value.failed + raised.value.undelivered == 2
