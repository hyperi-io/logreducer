"""Integration test: ClickHouseSource against the run's shared ClickHouse.

The query uses ClickHouse's built-in numbers() table function, so the test
writes nothing. Marked `integration`; deselect with `-m "not integration"`.
"""

import pytest

from logreducer import LogReducer

pytestmark = pytest.mark.integration

_QUERY = "SELECT concat('svc=api level=ERROR msg=timeout shard=', toString(number % 3)) AS line FROM numbers(60)"


def test_clickhouse_source_block_streaming(clickhouse_client):
    from logreducer.clickhouse import ClickHouseSource

    source = ClickHouseSource(clickhouse_client, _QUERY)

    lines = list(source)
    assert len(lines) == 60
    assert all(line.startswith("svc=api") for line in lines)

    # Re-iterable: a second pass re-runs the query and yields the same rows.
    assert list(source) == lines


def test_reduce_over_clickhouse_source(clickhouse_client):
    from logreducer.clickhouse import ClickHouseSource

    reducer = LogReducer(level="standard", mode="pattern")
    result = reducer.reduce(ClickHouseSource(clickhouse_client, _QUERY))
    # 3 distinct patterns in 60 rows -> a large reduction.
    assert 0 < len(result) < 60
    assert reducer.stats["input_lines"] == 60
