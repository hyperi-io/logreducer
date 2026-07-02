"""Unit tests for the sampling helpers (pure, no database needed)."""

import random

import pytest

from logreducer.sampling import (
    SamplingNotSupported,
    build_sample_batch_sql,
    build_sample_sql,
    build_table_sample_query,
    estimate_batch_rows,
    reservoir_sample,
)


class TestBuildSampleSql:
    def test_postgresql_seeded_sets_seed_and_predicate(self):
        setup, sql = build_sample_sql("postgresql", "SELECT msg FROM logs", 0.1, seed=42)
        assert setup is not None
        assert "setseed" in setup
        assert "random() <" in sql
        assert "SELECT msg FROM logs" in sql  # user query wrapped, not rewritten
        assert "_lr_sample" in sql

    def test_postgresql_unseeded_has_no_setup(self):
        setup, sql = build_sample_sql("postgresql", "SELECT msg FROM logs", 0.25)
        assert setup is None
        assert "random() <" in sql

    def test_mysql_uses_rand(self):
        setup, sql = build_sample_sql("mysql", "SELECT msg FROM logs", 0.1, seed=7)
        assert setup is None
        assert "rand(7)" in sql

    def test_sqlite_unseeded_ok(self):
        setup, sql = build_sample_sql("sqlite", "SELECT msg FROM logs", 0.1)
        assert setup is None
        assert "abs(random())" in sql

    def test_sqlite_seeded_raises(self):
        with pytest.raises(SamplingNotSupported, match="sqlite"):
            build_sample_sql("sqlite", "SELECT msg FROM logs", 0.1, seed=1)

    def test_unknown_dialect_raises(self):
        with pytest.raises(SamplingNotSupported, match="oracle"):
            build_sample_sql("oracle", "SELECT msg FROM logs", 0.1)

    @pytest.mark.parametrize("bad", [0.0, -0.1, 1.5, 2.0])
    def test_bad_fraction_raises(self, bad):
        with pytest.raises(ValueError, match="fraction"):
            build_sample_sql("postgresql", "SELECT 1", bad)


class TestBuildSampleBatchSql:
    def test_sqlite_orders_random_with_limit(self):
        sql = build_sample_batch_sql("sqlite", "SELECT msg FROM logs", 500)
        assert "ORDER BY random()" in sql
        assert "LIMIT 500" in sql
        assert "_lr_batch" in sql

    def test_clickhouse_uses_rand(self):
        sql = build_sample_batch_sql("clickhouse", "SELECT msg FROM logs", 100)
        assert "ORDER BY rand()" in sql
        assert "LIMIT 100" in sql

    def test_bad_size_raises(self):
        with pytest.raises(ValueError, match="positive"):
            build_sample_batch_sql("sqlite", "SELECT 1", 0)

    def test_unknown_dialect_raises(self):
        with pytest.raises(SamplingNotSupported):
            build_sample_batch_sql("nope", "SELECT 1", 10)


class TestBuildTableSampleQuery:
    def test_postgresql_system_with_repeatable(self):
        sql = build_table_sample_query("postgresql", '"logs"', '"msg"', fraction=0.1, seed=42)
        assert "TABLESAMPLE SYSTEM (10.0)" in sql
        assert "REPEATABLE (42)" in sql
        assert 'FROM "logs"' in sql

    def test_postgresql_bernoulli_method(self):
        sql = build_table_sample_query("postgresql", '"logs"', '"msg"', fraction=0.25, method="bernoulli")
        assert "TABLESAMPLE BERNOULLI (25.0)" in sql
        assert "REPEATABLE" not in sql  # no seed given

    def test_postgresql_where_clause(self):
        sql = build_table_sample_query("postgresql", '"logs"', '"msg"', fraction=0.1, where="level = 'ERROR'")
        assert "WHERE level = 'ERROR'" in sql

    def test_postgresql_bad_method_raises(self):
        with pytest.raises(ValueError, match="method"):
            build_table_sample_query("postgresql", '"t"', '"c"', fraction=0.1, method="nope")

    def test_mysql_predicate_fallback(self):
        sql = build_table_sample_query("mysql", "`logs`", "`msg`", fraction=0.1, seed=7)
        assert "rand(7)" in sql
        assert "TABLESAMPLE" not in sql

    def test_sqlite_predicate_and_seed_raises(self):
        sql = build_table_sample_query("sqlite", '"logs"', '"msg"', fraction=0.1)
        assert "abs(random())" in sql
        with pytest.raises(SamplingNotSupported):
            build_table_sample_query("sqlite", '"logs"', '"msg"', fraction=0.1, seed=1)

    def test_unknown_dialect_raises(self):
        with pytest.raises(SamplingNotSupported):
            build_table_sample_query("oracle", '"t"', '"c"', fraction=0.1)


class TestReservoirSample:
    def test_returns_all_when_k_ge_length(self):
        items = ["a", "b", "c"]
        out = reservoir_sample(items, 10, random.Random(0))
        assert sorted(out) == ["a", "b", "c"]

    def test_returns_exactly_k(self):
        items = [str(i) for i in range(10_000)]
        out = reservoir_sample(items, 100, random.Random(0))
        assert len(out) == 100
        assert set(out) <= set(items)  # only real items, no duplicates introduced
        assert len(set(out)) == 100  # without replacement

    def test_deterministic_with_seed(self):
        items = [str(i) for i in range(5000)]
        a = reservoir_sample(items, 50, random.Random(123))
        b = reservoir_sample(items, 50, random.Random(123))
        assert a == b

    def test_zero_k_is_empty(self):
        assert reservoir_sample(["a", "b"], 0, random.Random(0)) == []

    def test_roughly_uniform(self):
        # Halves of the stream should be represented roughly equally.
        items = [f"lo-{i}" for i in range(5000)] + [f"hi-{i}" for i in range(5000)]
        out = reservoir_sample(items, 1000, random.Random(1))
        lo = sum(1 for x in out if x.startswith("lo-"))
        assert 350 < lo < 650  # ~500 expected; generous band, not a flake


class TestEstimateBatchRows:
    def test_empty_sample_returns_floor(self):
        assert estimate_batch_rows([], 1_000_000, floor=1000) == 1000

    def test_zero_budget_returns_floor(self):
        assert estimate_batch_rows(["x" * 100], 0, floor=1000) == 1000

    def test_smaller_rows_allow_more(self):
        small = estimate_batch_rows(["x" * 10], 10_000_000, floor=1, ceil=10_000_000, align=1)
        big = estimate_batch_rows(["x" * 1000], 10_000_000, floor=1, ceil=10_000_000, align=1)
        assert small > big

    def test_clamped_to_ceil(self):
        rows = estimate_batch_rows(["x" * 5], 10**12, floor=1000, ceil=50_000, align=1000)
        assert rows == 50_000

    def test_aligned_to_multiple(self):
        rows = estimate_batch_rows(["x" * 100], 5_000_000, floor=1000, ceil=10_000_000, align=1000)
        assert rows % 1000 == 0
