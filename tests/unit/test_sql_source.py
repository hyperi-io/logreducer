"""Unit tests for SQLSource against a real (file-backed) SQLite database.

SQLite needs no server and no docker, so these run in the normal suite and give
genuine coverage of the SQLAlchemy streaming path (no mocks).
"""

import pytest

pytest.importorskip("sqlalchemy")

from logreducer import LogReducer
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
