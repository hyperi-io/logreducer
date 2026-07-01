"""Sampling helpers: dialect-aware SQL sampling, reservoir sampling, batch sizing.

Three concerns, all pure and server-free so they unit-test without a database:

* ``build_sample_sql`` - wrap an arbitrary user query in a deterministic,
  per-dialect random predicate so a fraction of rows is returned reproducibly
  (needed because ``TABLESAMPLE`` only applies to a base table, not the
  arbitrary ``SELECT`` a Source is given). Mirrors ibis: raise when a seed
  cannot be honoured deterministically rather than fake reproducibility.
* ``build_sample_batch_sql`` - one fresh random batch of ``n`` rows
  (``ORDER BY <rand> LIMIT n``) for the reduce-to-target loop (with-replacement).
* ``reservoir_sample`` (Algorithm L) and ``estimate_batch_rows`` - the
  client-side primitives the target orchestrator and the memory watchdog use.
"""

from __future__ import annotations

import math
import random
from collections.abc import Iterable
from itertools import islice


class SamplingNotSupported(Exception):
    """A sampling request an engine cannot honour (e.g. a seed on SQLite)."""


# Per-dialect random function, used by ORDER BY <rand> for fresh batches.
RANDOM_FN: dict[str, str] = {
    "postgresql": "random()",
    "mysql": "rand()",
    "mariadb": "rand()",
    "sqlite": "random()",
    "clickhouse": "rand()",
}


def _pg_sample(query: str, fraction: float, seed: int | None) -> tuple[str | None, str]:
    # setseed makes random() deterministic for the rest of the connection; it
    # takes a value in [-1, 1]. Each pass opens a fresh connection and re-seeds,
    # so the sample is identical across passes (re-iterable).
    setup = None
    if seed is not None:
        s = ((seed % 2_000_000) / 1_000_000.0) - 1.0
        setup = f"SELECT setseed({s!r})"
    return setup, f"SELECT * FROM ({query}) AS _lr_sample WHERE random() < {float(fraction)!r}"


def _mysql_sample(query: str, fraction: float, seed: int | None) -> tuple[str | None, str]:
    # RAND(seed) with a constant seed is a repeatable per-row sequence.
    rand = f"rand({int(seed)})" if seed is not None else "rand()"
    return None, f"SELECT * FROM ({query}) AS _lr_sample WHERE {rand} < {float(fraction)!r}"


def _sqlite_sample(query: str, fraction: float, seed: int | None) -> tuple[str | None, str]:
    if seed is not None:
        raise SamplingNotSupported(
            "sqlite has no seedable RNG, so seeded (reproducible) sampling is unsupported; "
            "omit sample_seed for best-effort sampling, or use a seedable engine (postgresql, mysql)"
        )
    threshold = int(float(fraction) * 1_000_000)
    return None, f"SELECT * FROM ({query}) AS _lr_sample WHERE (abs(random()) % 1000000) < {threshold}"


# dialect.name -> builder. ClickHouse is handled by its own source (native
# SAMPLE clause), so it is intentionally not here.
DIALECT_SAMPLERS = {
    "postgresql": _pg_sample,
    "mysql": _mysql_sample,
    "mariadb": _mysql_sample,
    "sqlite": _sqlite_sample,
}


def _check_fraction(fraction: float) -> None:
    if not (0.0 < fraction <= 1.0):
        raise ValueError(f"sample fraction must be in (0, 1], got {fraction!r}")


def build_sample_sql(dialect: str, query: str, fraction: float, seed: int | None = None) -> tuple[str | None, str]:
    """Wrap ``query`` so it returns ~``fraction`` of its rows, deterministically.

    Returns ``(setup_sql, sampled_sql)`` where ``setup_sql`` is an optional
    per-connection statement to run first (PostgreSQL ``setseed``), or None.

    Raises ``ValueError`` for a bad fraction and ``SamplingNotSupported`` for a
    dialect with no sampler or a seed the dialect cannot honour.
    """
    _check_fraction(fraction)
    builder = DIALECT_SAMPLERS.get(dialect)
    if builder is None:
        raise SamplingNotSupported(f"no SQL sampler for dialect {dialect!r} (supported: {sorted(DIALECT_SAMPLERS)})")
    return builder(query, fraction, seed)


def build_sample_batch_sql(dialect: str, query: str, n: int) -> str:
    """A fresh random batch of up to ``n`` rows (``ORDER BY <rand> LIMIT n``).

    Deliberately unseeded: each call returns a different sample (with-replacement),
    which is what the reduce-to-target loop wants.
    """
    if n <= 0:
        raise ValueError(f"batch size must be positive, got {n!r}")
    rand = RANDOM_FN.get(dialect)
    if rand is None:
        raise SamplingNotSupported(f"no random function for dialect {dialect!r} (supported: {sorted(RANDOM_FN)})")
    return f"SELECT * FROM ({query}) AS _lr_batch ORDER BY {rand} LIMIT {int(n)}"


def reservoir_sample(items: Iterable[str], k: int, rng: random.Random) -> list[str]:
    """Uniform sample of ``k`` items from a stream of unknown length (Algorithm L).

    Without replacement, O(k) memory, O(k(1 + log(n/k))) expected time. Replaces
    the old ``hash(line) % (i+1)`` reservoir, which was neither uniform nor
    reproducible (it depended on PYTHONHASHSEED). Seed ``rng`` for reproducibility.
    """
    if k <= 0:
        return []
    it = iter(items)
    reservoir = list(islice(it, k))
    if len(reservoir) < k:
        return reservoir  # fewer than k items - keep them all

    def _u() -> float:
        # Clamp away from 0.0 and 1.0 so log() and log1p(-w) never blow up.
        return min(max(rng.random(), 1e-12), 1.0 - 1e-12)

    w = math.exp(math.log(_u()) / k)
    while True:
        skip = math.floor(math.log(_u()) / math.log1p(-w))
        # islice(it, skip, skip + 1) discards `skip` items and yields the next.
        nxt = next(islice(it, skip, skip + 1), None)
        if nxt is None:
            return reservoir
        reservoir[rng.randrange(k)] = nxt
        w *= math.exp(math.log(_u()) / k)


def estimate_batch_rows(
    sample_lines: list[str],
    budget_bytes: int,
    *,
    floor: int = 1000,
    ceil: int = 1_000_000,
    align: int = 1000,
    overhead: int = 3,
) -> int:
    """Rows that fit ``budget_bytes``, from the average byte size of a sample.

    ``overhead`` approximates Python's per-object memory multiplier (matching
    MemoryMonitor). Result is clamped to ``[floor, ceil]`` and rounded down to a
    multiple of ``align`` so it lines up with the cursor fetch batch.
    """
    if not sample_lines or budget_bytes <= 0:
        return floor
    avg_bytes = sum(len(s.encode("utf-8")) for s in sample_lines) / len(sample_lines)
    per_row = max(1.0, avg_bytes * overhead)
    rows = int(budget_bytes / per_row)
    rows = max(floor, min(ceil, rows))
    if align > 1:
        rows = max(align, (rows // align) * align)
    return rows
