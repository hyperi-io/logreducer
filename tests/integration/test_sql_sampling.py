"""Integration tests: seeded/native SQL sampling against real PostgreSQL + MySQL.

Verifies what SQLite cannot: that the per-dialect sampling actually executes on
the real engine and that a seed makes the sample deterministic across passes
(required for the reducer's multi-pass modes). Docker-gated; skips without it.
No mocks - real engines via testcontainers, seeded read-only.
"""

import pytest

pytest.importorskip("sqlalchemy")

from logreducer import LogReducer, reduce_to_target
from logreducer.sql import SQLSource

pytestmark = pytest.mark.integration


class TestPostgreSQLSampling:
    def test_seeded_sample_is_deterministic_across_passes(self, pg_logs_engine):
        source = SQLSource(pg_logs_engine, "SELECT line FROM logs", sample=0.2, sample_seed=42)
        first = list(source)
        second = list(source)
        assert first == second  # setseed makes random() reproducible per pass
        assert 0 < len(first) < 5000

    def test_from_table_tablesample_repeatable(self, pg_logs_engine):
        a = list(SQLSource.from_table(pg_logs_engine, "logs", "line", sample=0.1, sample_seed=7))
        b = list(SQLSource.from_table(pg_logs_engine, "logs", "line", sample=0.1, sample_seed=7))
        assert a == b  # TABLESAMPLE ... REPEATABLE(7) is deterministic
        assert 0 < len(a) < 5000

    def test_from_table_bernoulli_method(self, pg_logs_engine):
        source = SQLSource.from_table(pg_logs_engine, "logs", "line", sample=0.1, method="bernoulli")
        assert 0 < len(list(source)) < 5000

    def test_sample_batch_returns_bounded_batch(self, pg_logs_engine):
        source = SQLSource(pg_logs_engine, "SELECT line FROM logs")
        batch = source.sample_batch(100)
        assert len(batch) == 100

    def test_reduce_to_target_over_postgres(self, pg_logs_engine):
        reducer = LogReducer(level="standard", mode="pattern")
        source = SQLSource(pg_logs_engine, "SELECT line FROM logs")
        outcome = reduce_to_target(source, reducer, target_rows=3, max_fetches=10)
        assert outcome["stats"]["collected"] > 0


class TestMySQLSampling:
    def test_seeded_sample_is_deterministic_across_passes(self, mysql_logs_engine):
        source = SQLSource(mysql_logs_engine, "SELECT line FROM logs", sample=0.2, sample_seed=42)
        first = list(source)
        second = list(source)
        assert first == second  # RAND(42) is a repeatable sequence
        assert 0 < len(first) < 5000

    def test_from_table_predicate_fallback(self, mysql_logs_engine):
        # MySQL has no TABLESAMPLE - from_table falls back to a RAND(seed) predicate.
        source = SQLSource.from_table(mysql_logs_engine, "logs", "line", sample=0.1, sample_seed=7)
        assert 0 < len(list(source)) < 5000
