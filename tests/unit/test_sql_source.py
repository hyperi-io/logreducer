"""Unit tests for SQLSource against a real (file-backed) SQLite database.

SQLite needs no server and no docker, so these run in the normal suite and give
genuine coverage of the SQLAlchemy streaming path (no mocks).
"""

import pytest

pytest.importorskip("sqlalchemy")

from logreducer import LogReducer, reduce_to_target
from logreducer.sampling import SamplingNotSupported
from logreducer.sql import SQLSource


@pytest.fixture
def sqlite_url(tmp_path):
    """A file-backed SQLite DB with a logs table; returns its SQLAlchemy URL."""
    from sqlalchemy import create_engine, text

    url = f"sqlite:///{tmp_path / 'logs.db'}"
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE logs (id INTEGER PRIMARY KEY, line TEXT)"))
        conn.execute(
            text("INSERT INTO logs (line) VALUES (:l)"),
            [{"l": f"ERROR request failed shard={i % 4}"} for i in range(100)],
        )
    engine.dispose()
    return url


def test_sqlsource_streams_lines(sqlite_url):
    source = SQLSource(sqlite_url, "SELECT line FROM logs ORDER BY id")
    lines = list(source)
    assert len(lines) == 100
    assert lines[0] == "ERROR request failed shard=0"


def test_sqlsource_is_reiterable(sqlite_url):
    source = SQLSource(sqlite_url, "SELECT line FROM logs")
    assert list(source) == list(source)


def test_sqlsource_skips_null_and_blank(tmp_path):
    from sqlalchemy import create_engine, text

    url = f"sqlite:///{tmp_path / 'x.db'}"
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE t (line TEXT)"))
        conn.execute(
            text("INSERT INTO t (line) VALUES (:l)"),
            [{"l": "keep"}, {"l": None}, {"l": "   "}, {"l": "also"}],
        )
    engine.dispose()
    assert list(SQLSource(url, "SELECT line FROM t")) == ["keep", "also"]


def test_reduce_over_sqlsource(sqlite_url):
    reducer = LogReducer(level="standard", mode="pattern")
    with SQLSource(sqlite_url, "SELECT line FROM logs") as source:
        result = reducer.reduce(source)
    assert 0 < len(result) < 100  # 4 distinct patterns -> big reduction


def test_sqlsource_rejects_bad_connectable():
    with pytest.raises(TypeError):
        SQLSource(1234, "SELECT 1")  # not an Engine or URL string


def test_sqlsource_sample_returns_subset(sqlite_url):
    # Unseeded SQLite sampling: a strict subset of the 100 rows.
    source = SQLSource(sqlite_url, "SELECT line FROM logs", sample=0.3)
    lines = list(source)
    assert 0 <= len(lines) < 100


def test_sqlsource_sample_seed_on_sqlite_raises(sqlite_url):
    # SQLite has no seedable RNG; a deterministic request must fail at build.
    with pytest.raises(SamplingNotSupported):
        SQLSource(sqlite_url, "SELECT line FROM logs", sample=0.3, sample_seed=1)


def test_sqlsource_sample_batch_size(sqlite_url):
    source = SQLSource(sqlite_url, "SELECT line FROM logs")
    batch = source.sample_batch(10)
    assert len(batch) == 10
    assert all(b.startswith("ERROR request failed") for b in batch)


def test_reduce_to_target_over_sqlsource(sqlite_url):
    # 4 distinct patterns in the table; ask for 3 - reached via sampled batches.
    reducer = LogReducer(level="standard", mode="pattern")
    source = SQLSource(sqlite_url, "SELECT line FROM logs")
    result = reduce_to_target(source, reducer, target_rows=3, max_fetches=10)
    assert result["stats"]["collected"] > 0
    assert result["stats"]["stop_reason"] in {"target", "plateau"}
