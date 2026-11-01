"""Sampling helpers: dialect-aware SQL sampling, reservoir sampling, batch sizing.

Three concerns, all pure and server-free so they unit-test without a database:

* ``build_sample_sql`` - wrap an arbitrary user query in a per-dialect predicate
  (a seeded row hash, or ``random()`` unseeded) so a fraction of rows is returned
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
from collections.abc import Iterable, Sequence
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


def _terminator_index(query: str) -> int | None:
    """Index of a ``;`` followed only by whitespace and comments, else None.

    One forward pass in linear time that skips quoted text and comments, so a
    ``;`` or ``--`` inside a string literal is never mistaken for syntax.
    """
    end = len(query)
    last_semicolon: int | None = None
    i = 0
    while i < end:
        char = query[i]
        if char == ";":
            last_semicolon = i
            i += 1
        elif char.isspace():
            i += 1
        elif query.startswith("--", i):
            newline = query.find("\n", i)
            i = end if newline < 0 else newline + 1
        elif query.startswith("/*", i):
            close = query.find("*/", i + 2)
            i = end if close < 0 else close + 2
        elif char in "'\"`":
            i += 1
            while i < end:
                if query[i] == char:
                    if query.startswith(char, i + 1):  # a doubled quote is an escaped quote
                        i += 2
                        continue
                    break
                i += 1
            i += 1
            last_semicolon = None
        else:
            last_semicolon = None
            i += 1
    return last_semicolon


def wrap_subquery(query: str) -> str:
    """The query as text safe to place inside ``( ... )``.

    A trailing ``;`` is a syntax error inside a subquery, and a trailing ``--``
    comment swallows the closing parenthesis, so the terminator is dropped and
    the text ends on a newline.
    """
    query = query.strip()
    terminator = _terminator_index(query)
    if terminator is not None:
        query = query[:terminator]
    return query.rstrip() + "\n"


# A seeded sample keeps a row when the first 32 bits of md5(row text + seed) fall under
# fraction * 2**32, so the same row gets the same verdict however the engine scans.
_HASH_SPACE = 2**32


def _hash_threshold(fraction: float) -> int:
    return int(float(fraction) * _HASH_SPACE)


def _pg_sample(
    query: str, fraction: float, seed: int | None, columns: Sequence[str] | None = None
) -> tuple[str | None, str]:
    wrapped = f"SELECT * FROM ({wrap_subquery(query)}) AS _lr_sample"
    if seed is None:
        return None, f"{wrapped} WHERE random() < {float(fraction)!r}"
    row_hash = f"('x' || lpad(substr(md5(_lr_sample::text || '{int(seed)}'), 1, 8), 16, '0'))::bit(64)::bigint"
    return None, f"{wrapped} WHERE {row_hash} < {_hash_threshold(fraction)}"


def _mysql_sample(
    query: str, fraction: float, seed: int | None, columns: Sequence[str] | None = None
) -> tuple[str | None, str]:
    wrapped = f"SELECT * FROM ({wrap_subquery(query)}) AS _lr_sample"
    if seed is None:
        return None, f"{wrapped} WHERE rand() < {float(fraction)!r}"
    if not columns:
        raise ValueError("a seeded MySQL sample needs the query's quoted column names")
    row_text = f"CONCAT_WS(CHAR(31), {', '.join(columns)}, '{int(seed)}')"
    return None, f"{wrapped} WHERE CONV(SUBSTRING(MD5({row_text}), 1, 8), 16, 10) < {_hash_threshold(fraction)}"


def _sqlite_sample(
    query: str, fraction: float, seed: int | None, columns: Sequence[str] | None = None
) -> tuple[str | None, str]:
    if seed is not None:
        raise SamplingNotSupported(
            "sqlite has no seedable RNG, so seeded (reproducible) sampling is unsupported; "
            "omit sample_seed for best-effort sampling, or use a seedable engine (postgresql, mysql)"
        )
    threshold = int(float(fraction) * 1_000_000)
    return None, f"SELECT * FROM ({wrap_subquery(query)}) AS _lr_sample WHERE (abs(random()) % 1000000) < {threshold}"


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


def build_sample_sql(
    dialect: str, query: str, fraction: float, seed: int | None = None, columns: Sequence[str] | None = None
) -> tuple[str | None, str]:
    """Wrap ``query`` so it returns ~``fraction`` of its rows.

    With a seed, a row is kept by a hash of its content and the seed, so the same
    rows come back whatever order the engine reads them in.

    Returns ``(setup_sql, sampled_sql)`` where ``setup_sql`` is an optional
    per-connection statement to run first, or None.

    Args:
        dialect: SQLAlchemy dialect name.
        query: The SELECT to sample.
        fraction: Share of rows to keep, in (0, 1].
        seed: Seed for a reproducible sample.
        columns: The query's column names, quoted. A seeded MySQL sample needs
            them to hash the row.

    Raises:
        ValueError: For a bad fraction, or a seeded MySQL sample without ``columns``.
        SamplingNotSupported: For a dialect with no sampler or a seed it cannot honour.
    """
    _check_fraction(fraction)
    builder = DIALECT_SAMPLERS.get(dialect)
    if builder is None:
        raise SamplingNotSupported(f"no SQL sampler for dialect {dialect!r} (supported: {sorted(DIALECT_SAMPLERS)})")
    return builder(query, fraction, seed, columns)


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
    return f"SELECT * FROM ({wrap_subquery(query)}) AS _lr_batch ORDER BY {rand} LIMIT {int(n)}"


def build_table_sample_query(
    dialect: str,
    table: str,
    column: str,
    *,
    fraction: float,
    seed: int | None = None,
    method: str = "system",
    where: str | None = None,
) -> str:
    """Build a native table-sampling query (``table``/``column`` already quoted).

    PostgreSQL uses page-level ``TABLESAMPLE SYSTEM`` (or row-level ``BERNOULLI``)
    with ``REPEATABLE(seed)`` - genuinely sub-linear, unlike the full-scan random
    predicate used for arbitrary queries. Engines without TABLESAMPLE (MySQL,
    SQLite) fall back to a predicate on the table (still a full scan).

    Raises ``SamplingNotSupported`` for a dialect with no table sampler or a seed
    it cannot honour, and ``ValueError`` for a bad fraction or method.
    """
    _check_fraction(fraction)
    conds = [where] if where else []

    if dialect == "postgresql":
        m = method.lower()
        if m not in ("system", "bernoulli"):
            raise ValueError(f"method must be 'system' or 'bernoulli', got {method!r}")
        pct = float(fraction) * 100.0
        repeatable = f" REPEATABLE ({int(seed)})" if seed is not None else ""
        where_sql = f" WHERE {' AND '.join(conds)}" if conds else ""
        return f"SELECT {column} FROM {table} TABLESAMPLE {m.upper()} ({pct!r}){repeatable}{where_sql}"

    # No TABLESAMPLE on these - a predicate on the table (full scan, but native).
    if dialect in ("mysql", "mariadb"):
        if seed is None:
            pred = f"rand() < {float(fraction)!r}"
        else:
            row_hash = f"CONV(SUBSTRING(MD5(CONCAT_WS(CHAR(31), {column}, '{int(seed)}')), 1, 8), 16, 10)"
            pred = f"{row_hash} < {_hash_threshold(fraction)}"
    elif dialect == "sqlite":
        if seed is not None:
            raise SamplingNotSupported("sqlite has no seedable RNG; seeded table sampling is unsupported")
        pred = f"(abs(random()) % 1000000) < {int(float(fraction) * 1_000_000)}"
    else:
        raise SamplingNotSupported(f"no table sampler for dialect {dialect!r}")

    conds.append(pred)
    return f"SELECT {column} FROM {table} WHERE {' AND '.join(conds)}"


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
    avg_bytes = sum(len(s.encode("utf-8", "surrogatepass")) for s in sample_lines) / len(sample_lines)
    per_row = max(1.0, avg_bytes * overhead)
    rows = int(budget_bytes / per_row)
    if align > 1:
        rows = (rows // align) * align
    # Clamp LAST so alignment can never push the result outside [floor, ceil].
    return max(floor, min(ceil, rows))
