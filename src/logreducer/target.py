"""Reduce-to-target orchestrator.

Where ``LogReducer.reduce`` makes a single pass over a whole source, this pulls
fresh random batches and reduces them one at a time, accumulating distinct
representative lines until it has the number the caller asked for - or the
source runs dry, a fetch cap is hit, or the representatives stop growing.

Peak memory is bounded to roughly one batch plus the accumulator: batches are
sized to a byte budget (from the observed average row size), and a psutil
watchdog shrinks the batch and, as a hard backstop, stops the loop under
pressure. This is the memory-safe path for "give me X lines from a huge table"
without a full scan.

Batches come from ``source.sample_batch(n)`` where the source supports it (SQL,
ClickHouse); any other re-iterable falls back to a client-side reservoir sample
over the source per round.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from .memory import MemoryMonitor
from .sampling import estimate_batch_rows, reservoir_sample

if TYPE_CHECKING:
    from .core import LogReducer
    from .sources import Source

_DEFAULT_BATCH_ROWS = 10_000
_MIN_BATCH_ROWS = 1_000


@runtime_checkable
class _Sampleable(Protocol):
    """A source that can hand back a fresh random batch of ``n`` lines."""

    def sample_batch(self, n: int) -> list[str]: ...


def _pull_batch(source: Source, n: int, rng: random.Random) -> list[str]:
    """One fresh random batch of up to ``n`` lines.

    Uses the source's own ``sample_batch`` (SQL/ClickHouse do it in the engine);
    otherwise reservoir-samples the whole re-iterable client-side - correct, but
    it re-reads the source each round, so it is best for in-memory or file
    sources rather than remote ones.
    """
    if isinstance(source, _Sampleable):
        return source.sample_batch(n)
    return reservoir_sample(iter(source), n, rng)


def reduce_to_target(
    source: Source,
    reducer: LogReducer,
    *,
    target_rows: int,
    max_fetches: int = 50,
    max_batch_memory_gb: float | None = None,
    batch_rows: int | None = None,
    plateau_rounds: int = 2,
    seed: int | None = None,
) -> dict[str, Any]:
    """Accumulate reduced representative lines until ``target_rows`` are found.

    Args:
        source: The data source. If it has ``sample_batch(n)`` (SQL, ClickHouse)
            each round draws a fresh random batch from the engine; otherwise the
            whole source is reservoir-sampled per round.
        reducer: A configured ``LogReducer``. Reused across batches - its state
            is reset per ``reduce()`` call, so each batch is reduced independently.
        target_rows: How many distinct representative lines to collect.
        max_fetches: Hard cap on batch pulls (backstop against a source that
            never yields enough distinct representatives).
        max_batch_memory_gb: Byte budget a batch must fit; batch size is derived
            from the observed average row size. Also arms the memory watchdog.
            Defaults to the reducer's own ``max_memory_gb``.
        batch_rows: Fixed batch size; disables adaptive sizing when set.
        plateau_rounds: Stop after this many consecutive batches that add no new
            representatives (a low-cardinality source may never reach the target).
        seed: Seed for the client-side reservoir fallback (ignored when the
            source samples in the engine).

    Returns:
        ``{"lines": [...], "stats": {...}}`` - up to ``target_rows`` lines plus
        counts and the stop reason (``target`` / ``exhausted`` / ``max_fetches``
        / ``plateau`` / ``memory``).
    """
    if target_rows <= 0:
        raise ValueError(f"target_rows must be positive, got {target_rows!r}")
    if max_fetches <= 0:
        raise ValueError(f"max_fetches must be positive, got {max_fetches!r}")
    if batch_rows is not None and batch_rows <= 0:
        raise ValueError(f"batch_rows must be positive, got {batch_rows!r}")
    if plateau_rounds <= 0:
        raise ValueError(f"plateau_rounds must be positive, got {plateau_rounds!r}")

    # As documented: the byte budget defaults to the reducer's own memory cap,
    # so adaptive batch sizing is on by default (pass batch_rows to fix it).
    budget_gb = max_batch_memory_gb if max_batch_memory_gb is not None else reducer.config.max_memory_gb
    monitor = MemoryMonitor(budget_gb)
    budget_bytes = int(budget_gb * 1024**3)
    rng = random.Random(seed)

    seen: dict[str, None] = {}
    batch = batch_rows if batch_rows is not None else _DEFAULT_BATCH_ROWS
    fetches = 0
    plateau = 0
    reason = "max_fetches"

    while len(seen) < target_rows and fetches < max_fetches:
        lines = _pull_batch(source, batch, rng)
        fetches += 1
        if not lines:
            reason = "exhausted"
            break

        # Size the next batch from the bytes we just observed (adaptive mode).
        if budget_bytes and batch_rows is None:
            batch = estimate_batch_rows(lines, budget_bytes)

        added = 0
        for line in reducer.reduce(lines):
            if line not in seen:
                seen[line] = None
                added += 1
                if len(seen) >= target_rows:
                    break

        if len(seen) >= target_rows:
            reason = "target"
            break

        if added == 0:
            plateau += 1
            if plateau >= plateau_rounds:
                reason = "plateau"
                break
        else:
            plateau = 0

        # Watchdog: soft-shrink the next batch under pressure; hard-stop if the
        # limit is genuinely exceeded after a GC.
        _, safe = monitor.check_memory()
        if not safe:
            batch = max(_MIN_BATCH_ROWS, batch // 2)
            if monitor.is_limit_exceeded():
                reason = "memory"
                break

    result = list(seen)[:target_rows]
    return {
        "lines": result,
        "stats": {
            "target_rows": target_rows,
            "collected": len(result),
            "fetches": fetches,
            "final_batch_rows": batch,
            "peak_memory_gb": monitor.get_peak_usage_gb(),
            "stop_reason": reason,
        },
    }
