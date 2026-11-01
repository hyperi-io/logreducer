"""Kafka input source and output sink for logreducer (optional ``kafka`` extra).

Consume log lines from a Kafka topic to reduce them, and/or produce the reduced
lines back to a topic. Built on ``confluent-kafka`` (librdkafka).

The client defaults (``PRODUCER_DEFAULTS`` / ``CONSUMER_DEFAULTS``, librdkafka
config names), the ``merge_config`` / credential-masking idioms and the
``KafkaConsumerError`` / ``_PARTITION_EOF`` handling follow standard
production Kafka client practice, so a config authored for another
librdkafka-based client behaves the same here.

Two intentional consumer design choices, because a logreducer ``Source`` must
be finite and re-iterable (the reducer counts lines by exhausting the source,
and re-reads it for multi-pass modes):

* **Bounded.** The read records each partition's end offset when it is assigned
  and stops once every partition has reached it, by offset or by
  ``_PARTITION_EOF``. Messages written after that point wait for the next read.
  A consecutive-idle-poll count is only a backstop for a stalled broker.
* **No commit.** Offsets are never committed, so each pass re-reads from the
  earliest offset - that is what makes the source re-iterable. An application
  that needs offset tracking should consume itself and hand the reducer its own
  iterable of ``str``.

Install: ``pip install 'logreducer[kafka]'``.
"""

import importlib.util
import time
from collections.abc import Iterable, Iterator
from typing import Any

# Production-lean librdkafka defaults: durable produces, bounded timeouts,
# cheap batching. Any key can be overridden by the user config.
PRODUCER_DEFAULTS: dict[str, Any] = {
    "acks": "all",  # Wait for all replicas (durability)
    "retries": 5,  # Retry on transient failures
    "retry.backoff.ms": 100,  # Backoff between retries
    "delivery.timeout.ms": 120000,  # 2 minutes max delivery time
    "request.timeout.ms": 30000,  # 30 seconds per request
    "linger.ms": 5,  # Small delay for batching
    "compression.type": "lz4",  # Fast compression
    "batch.size": 16384,  # 16KB batch size
}

CONSUMER_DEFAULTS: dict[str, Any] = {
    "auto.offset.reset": "earliest",  # Start from beginning if no offset
    "enable.auto.commit": False,  # Manual control (this source never commits)
    "session.timeout.ms": 45000,  # 45 seconds session timeout
    "heartbeat.interval.ms": 3000,  # 3 seconds heartbeat
    "max.poll.interval.ms": 300000,  # 5 minutes max poll interval
    "fetch.min.bytes": 1,  # Return immediately with any data
    "fetch.wait.max.ms": 500,  # Max wait for fetch.min.bytes
    # A partition that ends in records the consumer skips (transaction markers, compacted
    # offsets) is known to be read through only by its EOF event.
    "enable.partition.eof": True,
}

_CREDENTIAL_KEYS: frozenset[str] = frozenset(
    {
        "sasl.password",
        "sasl.username",
        "ssl.key.password",
        "ssl.keystore.password",
        "ssl.truststore.password",
    }
)

_INSTALL_HINT = (
    "logreducer's Kafka source/sink needs confluent-kafka. Install the extra:\n    pip install 'logreducer[kafka]'"
)


def merge_config(user_config: dict[str, Any], defaults: dict[str, Any], verify_ssl: bool = True) -> dict[str, Any]:
    """Overlay ``user_config`` on ``defaults``; optionally disable TLS verify.

    User values win over defaults.
    """
    merged = {**defaults, **user_config}
    if not verify_ssl:
        merged["enable.ssl.certificate.verification"] = "false"
    return merged


def mask_credentials(config: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``config`` with credential values replaced by ``***``.

    Used in ``__repr__`` so a Kafka config never leaks secrets into logs.
    """
    return {k: ("***" if k in _CREDENTIAL_KEYS and v not in (None, "") else v) for k, v in config.items()}


class KafkaConsumerError(Exception):
    """A fatal Kafka consumer error, carrying the broker error code if known."""

    def __init__(self, message: str, error_code: int | None = None) -> None:
        self.error_code = error_code
        super().__init__(message)


class KafkaDeliveryError(Exception):
    """One or more produced messages were not delivered to the broker."""

    def __init__(self, message: str, failed: int, undelivered: int) -> None:
        self.failed = failed
        self.undelivered = undelivered
        super().__init__(message)


def _normalise_config(config: str | dict[str, Any]) -> dict[str, Any]:
    """A bare string is treated as ``bootstrap.servers``; a dict is copied."""
    if isinstance(config, str):
        return {"bootstrap.servers": config}
    return dict(config)


class KafkaSource:
    """A bounded, re-iterable stream of log lines from a Kafka topic.

    Each iteration creates a fresh consumer, subscribes, and reads every partition
    up to the end offset it had when assigned, decoding each message value to a
    ``str`` line. Offsets are never committed,
    so every pass re-reads from the earliest offset.
    """

    def __init__(
        self,
        config: str | dict[str, Any],
        group_id: str,
        topics: str | list[str],
        *,
        verify_ssl: bool = True,
        max_messages: int | None = None,
        poll_timeout: float = 1.0,
        idle_polls: int = 3,
        assignment_timeout: float = 30.0,
        encoding: str = "utf-8",
    ) -> None:
        """Build a Kafka source.

        Args:
            config: ``bootstrap.servers`` string, or a full librdkafka config.
            group_id: Consumer group id.
            topics: A topic name or list of names to subscribe to.
            verify_ssl: If False, disable TLS certificate verification.
            max_messages: Optional hard cap on lines read per pass.
            poll_timeout: Seconds to block per ``poll`` call.
            idle_polls: Backstop for a never-EOF broker - once partitions are
                assigned, stop after this many consecutive empty polls.
            assignment_timeout: Backstop for the never-assigned case (unreachable
                broker, missing topic, auth failure). If no partition is assigned
                within this many seconds, iteration raises instead of hanging.
            encoding: Text encoding for decoding message values.
        """
        if importlib.util.find_spec("confluent_kafka") is None:  # pragma: no cover - only without the extra
            raise ImportError(_INSTALL_HINT)

        config = _normalise_config(config)
        config["group.id"] = group_id
        self._config = merge_config(config, CONSUMER_DEFAULTS, verify_ssl=verify_ssl)
        self.topics = [topics] if isinstance(topics, str) else list(topics)
        self.max_messages = max_messages
        self.poll_timeout = poll_timeout
        self.idle_polls = idle_polls
        self.assignment_timeout = assignment_timeout
        self.encoding = encoding

    def __iter__(self) -> Iterator[str]:
        from confluent_kafka import Consumer, KafkaError

        consumer = Consumer(self._config)
        consumer.subscribe(self.topics)
        # End offset of each partition when first assigned: the read stops there, so a write
        # made during it is left for the next pass.
        end_offsets: dict[tuple[str, int], int] = {}
        drained: set[tuple[str, int]] = set()
        empty_polls = 0
        emitted = 0
        # Never-assigned backstop: an unreachable broker, a missing topic, or an
        # auth failure leaves assignment() empty forever, so empty_polls (gated
        # on assignment) never fires and the loop would spin indefinitely. Bail
        # if no partition is ever assigned within the timeout - a stuck
        # dependency surfaced as a real error, not a silent hang.
        ever_assigned = False
        assignment_deadline = time.monotonic() + self.assignment_timeout
        try:
            while True:
                if self.max_messages is not None and emitted >= self.max_messages:
                    break

                msg = consumer.poll(self.poll_timeout)

                assignment = consumer.assignment()
                if assignment:
                    ever_assigned = True
                    self._record_end_offsets(consumer, assignment, end_offsets, drained)
                    if drained >= end_offsets.keys():
                        break
                elif not ever_assigned and time.monotonic() >= assignment_deadline:
                    raise KafkaConsumerError(
                        f"no partition assignment within {self.assignment_timeout:.0f}s for "
                        f"topics {self.topics!r} (broker unreachable, missing topic, or auth failure?)"
                    )

                if msg is None:
                    # Before partitions are assigned an empty poll just means the
                    # group is still joining - don't count it. Once assigned,
                    # repeated empties are the backstop for a never-EOF broker.
                    if assignment:
                        empty_polls += 1
                        if empty_polls >= self.idle_polls:
                            break
                    continue
                empty_polls = 0

                partition_key = (msg.topic(), msg.partition())
                error = msg.error()
                if error:
                    if error.code() == KafkaError._PARTITION_EOF:
                        drained.add(partition_key)
                        continue
                    raise KafkaConsumerError(f"Kafka error: {error.str()}", error_code=error.code())

                end = end_offsets.get(partition_key)
                offset = msg.offset()
                if end is not None and offset is not None and offset >= end - 1:
                    drained.add(partition_key)
                    if offset >= end:
                        continue

                value = msg.value()
                if value is None:
                    continue
                line = value.decode(self.encoding, errors="replace").strip()
                if line:
                    emitted += 1
                    yield line
        finally:
            consumer.close()

    def _record_end_offsets(
        self,
        consumer: Any,
        assignment: list[Any],
        end_offsets: dict[tuple[str, int], int],
        drained: set[tuple[str, int]],
    ) -> None:
        """Record the high watermark of each newly assigned partition, marking empty ones drained."""
        from confluent_kafka import KafkaException

        for tp in assignment:
            key = (tp.topic, tp.partition)
            if key in end_offsets:
                continue
            try:
                low, high = consumer.get_watermark_offsets(tp, timeout=self.assignment_timeout, cached=False)
            except KafkaException as exc:
                raise KafkaConsumerError(f"cannot read the end offset of {key!r}: {exc}") from exc
            end_offsets[key] = high
            if high <= low:
                drained.add(key)

    def __repr__(self) -> str:
        return f"KafkaSource(topics={self.topics!r}, config={mask_credentials(self._config)!r})"


class KafkaSink:
    """A Sink that produces reduced lines to a Kafka topic.

    ``write`` produces each line as a UTF-8 message value and flushes at the
    end, returning the number of lines produced. Uses the standard
    produce/poll/flush shape over ``PRODUCER_DEFAULTS``.
    """

    def __init__(
        self,
        config: str | dict[str, Any],
        topic: str,
        *,
        key: str | None = None,
        verify_ssl: bool = True,
        flush_timeout: float | None = None,
        encoding: str = "utf-8",
    ) -> None:
        """Build a Kafka sink.

        Args:
            config: ``bootstrap.servers`` string, or a full librdkafka config.
            topic: Target topic for produced lines.
            key: Optional fixed message key applied to every line.
            verify_ssl: If False, disable TLS certificate verification.
            flush_timeout: Seconds to wait on the final flush (None = infinite).
            encoding: Text encoding for the produced message values.
        """
        try:
            from confluent_kafka import Producer
        except ImportError as exc:  # pragma: no cover - exercised only without the extra
            raise ImportError(_INSTALL_HINT) from exc

        self._config = merge_config(_normalise_config(config), PRODUCER_DEFAULTS, verify_ssl=verify_ssl)
        self.topic = topic
        self.key = key
        self.flush_timeout = flush_timeout
        self.encoding = encoding
        self._producer = Producer(self._config)

    def write(self, lines: Iterable[str]) -> int:
        """Produce each line to the topic and flush; return the number delivered.

        With the default ``flush_timeout=None`` the final flush blocks until the
        queue drains.

        Raises:
            KafkaDeliveryError: A message was rejected by the broker, expired
                before delivery, or was still queued when a finite
                ``flush_timeout`` ran out.
        """
        key_bytes = self.key.encode(self.encoding) if self.key is not None else None
        produced = 0
        errors: list[str] = []

        def on_delivery(err: Any, _msg: Any) -> None:
            if err is not None:
                errors.append(str(err))

        for line in lines:
            self._producer.produce(self.topic, value=line.encode(self.encoding), key=key_bytes, on_delivery=on_delivery)
            self._producer.poll(0)  # Trigger delivery callbacks (non-blocking)
            produced += 1
        undelivered = self.flush()
        if errors or undelivered:
            raise KafkaDeliveryError(
                f"{len(errors)} of {produced} messages failed and {undelivered} were still queued "
                f"for topic {self.topic!r}" + (f" (first error: {errors[0]})" if errors else ""),
                failed=len(errors),
                undelivered=undelivered,
            )
        return produced

    def flush(self) -> int:
        """Wait for outstanding messages; return the count still in queue."""
        if self.flush_timeout is not None:
            result: int = self._producer.flush(self.flush_timeout)
        else:
            result = self._producer.flush()
        return result

    def __enter__(self) -> KafkaSink:
        return self

    def __exit__(self, *exc: object) -> None:
        self.flush()

    def __repr__(self) -> str:
        return f"KafkaSink(topic={self.topic!r}, config={mask_credentials(self._config)!r})"
