"""Memory management and monitoring utilities."""

import gc
import os
import random
from collections import deque
from collections.abc import Callable, Iterable, Iterator
from typing import Any, Protocol

import psutil


class MemoryMonitor:
    """Monitor and control memory usage during processing."""

    def __init__(self, max_memory_gb: float = 1.0):
        self.max_memory_gb = max_memory_gb
        self.max_memory_bytes = max_memory_gb * 1024 * 1024 * 1024
        self.effective_limit = self.max_memory_bytes * 0.8  # 80% safety margin
        self.process = psutil.Process()
        self.peak_usage_bytes = 0

        # Initialize peak usage
        current_usage = self.process.memory_info().rss
        self.peak_usage_bytes = current_usage

        # Calculate safe parameters
        avg_line_size = 200  # bytes
        python_overhead = 3
        self.max_lines_in_memory = int(self.effective_limit / (avg_line_size * python_overhead))
        self.safe_chunk_size = max(1000, self.max_lines_in_memory // 10)

    def check_memory(self) -> tuple[float, bool]:
        """Return (current_gb, is_safe) against the SOFT 80% threshold.

        Not a pure getter: when the soft threshold is crossed this runs a
        gc.collect() and re-tests, so transient garbage does not trigger
        degradation. Callers use this as the soft tier and
        ``is_limit_exceeded`` (the full limit) as the hard tier.
        """
        current = self.process.memory_info().rss
        current_gb = current / (1024**3)
        is_safe = current < self.effective_limit

        # Update peak usage
        if current > self.peak_usage_bytes:
            self.peak_usage_bytes = current

        if not is_safe:
            gc.collect()
            current = self.process.memory_info().rss
            current_gb = current / (1024**3)
            is_safe = current < self.effective_limit

        return current_gb, is_safe

    def get_current_usage_gb(self) -> float:
        """Get current memory usage in GB."""
        current = self.process.memory_info().rss
        # Update peak usage
        if current > self.peak_usage_bytes:
            self.peak_usage_bytes = current
        return float(current / (1024**3))

    def get_peak_usage_gb(self) -> float:
        """Get peak memory usage in GB."""
        # Update current peak if needed
        current = self.process.memory_info().rss
        if current > self.peak_usage_bytes:
            self.peak_usage_bytes = current
        return self.peak_usage_bytes / (1024**3)

    def is_limit_exceeded(self) -> bool:
        """True when RSS exceeds the FULL configured limit (the hard tier).

        Deliberately compares against ``max_memory_bytes``, not the 80%
        ``effective_limit`` used by ``check_memory`` - the gap between the two
        is what gives callers room to soft-degrade (shrink batches, sample)
        before the hard stop fires.
        """
        current = self.process.memory_info().rss
        return bool(current > self.max_memory_bytes)

    def reset(self) -> None:
        """Reset peak memory tracking."""
        current_usage = self.process.memory_info().rss
        self.peak_usage_bytes = current_usage

    def estimate_file_strategy(self, file_size_bytes: int) -> str:
        """Determine processing strategy."""
        file_size_gb = file_size_bytes / (1024**3)

        if file_size_gb < self.max_memory_gb * 0.2:
            return "full"
        elif file_size_gb < self.max_memory_gb * 5:
            return "chunked"
        else:
            return "sampled"


class StreamingProcessor:
    """Process large files with constant memory usage."""

    def __init__(self, memory_monitor: MemoryMonitor):
        self.memory_monitor = memory_monitor
        self.chunk_size = memory_monitor.safe_chunk_size

    def read_file_streaming(self, file_path: str, tap: Callable[[str], None] | None = None) -> Iterator[str]:
        """Read file with minimal memory usage.

        Args:
            file_path: The file to read.
            tap: Called with every non-empty stripped line as it is read, before any sampling
                drops it, whichever strategy the file's size and the memory left select.
        """
        file_size = os.path.getsize(file_path)
        strategy = self.memory_monitor.estimate_file_strategy(file_size)

        if strategy == "full":
            with open(file_path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        if tap:
                            tap(line)
                        yield line

        elif strategy == "chunked":
            yield from self._read_chunked(file_path, tap)

        else:  # sampled
            yield from self._read_sampled(file_path, tap)

    def _read_chunked(self, file_path: str, tap: Callable[[str], None] | None = None) -> Iterator[str]:
        """Read file in chunks, degrading to sampling under memory pressure.

        The memory check runs on its own line counter, NOT on chunk-flush
        boundaries - a flush count and a line count almost never coincide, so
        gating the check on both used to make this fallback effectively dead.
        """
        chunk: list[str] = []
        check_every = 100_000
        next_check = check_every

        with open(file_path, encoding="utf-8", errors="replace") as f:
            for line_num, raw in enumerate(line.strip() for line in f):
                if not raw:
                    continue

                if tap:
                    tap(raw)
                chunk.append(raw)

                if len(chunk) >= self.chunk_size:
                    yield from chunk
                    chunk = []

                if line_num >= next_check:
                    next_check += check_every
                    _, is_safe = self.memory_monitor.check_memory()
                    if not is_safe:
                        yield from chunk
                        yield from self._read_sampled_remainder(f, tap)
                        return

            if chunk:
                yield from chunk

    def _read_sampled(self, file_path: str, tap: Callable[[str], None] | None = None) -> Iterator[str]:
        """Reservoir sampling for huge files (uniform, reproducible).

        Uses Algorithm L with a fixed-seed RNG so every pass over this
        re-iterable FileSource yields the SAME sample - the reducer's multi-pass
        modes need a stable input. (The old ``hash(line) % (i+1)`` reservoir was
        neither uniform nor stable across processes.)
        """
        from .sampling import reservoir_sample

        reservoir_size = min(self.chunk_size, 100000)

        def _lines() -> Iterator[str]:
            with open(file_path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    stripped = line.strip()
                    if stripped:
                        if tap:
                            tap(stripped)
                        yield stripped

        yield from reservoir_sample(_lines(), reservoir_size, random.Random(0))

    def _read_sampled_remainder(self, file_handle: Any, tap: Callable[[str], None] | None = None) -> Iterator[str]:
        """Reservoir-sample the rest of an already-open file (mid-chunk fallback)."""
        from .sampling import reservoir_sample

        def _lines() -> Iterator[str]:
            for line in file_handle:
                stripped = line.strip()
                if stripped:
                    if tap:
                        tap(stripped)
                    yield stripped

        yield from reservoir_sample(_lines(), 10000, random.Random(0))


class _Counted(Protocol):
    """Anything with a running ``count`` (a ``LogPattern``)."""

    count: int


class Occurrence:
    """Ties a line that survived exact dedup to the pattern it was merged into.

    Dedup drops later repeats of the line. Once a consumer sets ``target``, each
    dropped repeat adds one to ``target.count``, so a line seen 100 times
    counts 100 towards its pattern instead of 1.
    """

    __slots__ = ("target",)

    def __init__(self) -> None:
        self.target: _Counted | None = None

    def repeat(self) -> None:
        """Record one dropped repeat of the line."""
        if self.target is not None:
            self.target.count += 1


class BoundedDeduplicator:
    """Memory-bounded exact deduplication (sliding-window semantics).

    The seen-set is capped at ``max_cache_size`` hashes with FIFO eviction, so
    on very high-cardinality input a line can re-emit after its hash has been
    evicted - bounded memory is traded for global dedup guarantees.
    """

    def __init__(self, max_cache_size: int = 100000, hash_algorithm: str = "xxhash"):
        if max_cache_size < 1:
            raise ValueError(f"max_cache_size must be at least 1, got {max_cache_size!r}")
        self.max_cache_size = max_cache_size

        # Choose hash function. surrogatepass keeps a lone surrogate in a
        # caller-supplied line hashable instead of raising mid-run.
        if hash_algorithm == "xxhash":
            try:
                import xxhash

                self.hash_func = lambda x: xxhash.xxh64(x.encode("utf-8", "surrogatepass")).hexdigest()
            except ImportError:
                import hashlib

                self.hash_func = lambda x: hashlib.blake2b(
                    x.encode("utf-8", "surrogatepass"), digest_size=16
                ).hexdigest()
        else:
            import hashlib

            self.hash_func = lambda x: hashlib.md5(
                x.encode("utf-8", "surrogatepass"), usedforsecurity=False
            ).hexdigest()

        self.seen_hashes: deque[str] = deque(maxlen=max_cache_size)
        self.seen_set: set[str] = set()
        self._occurrences: dict[str, Occurrence] = {}
        self.stats = {"total": 0, "unique": 0, "duplicates": 0}

    def is_duplicate(self, line: str) -> bool:
        """Check if line is duplicate."""
        return self._observe(line)[0]

    def _observe(self, line: str) -> tuple[bool, Occurrence]:
        """Record ``line``, returning (is_duplicate, the Occurrence of its first sighting)."""
        self.stats["total"] += 1
        line_hash = self.hash_func(line)

        if line_hash in self.seen_set:
            self.stats["duplicates"] += 1
            occurrence = self._occurrences[line_hash]
            occurrence.repeat()
            return True, occurrence

        if len(self.seen_hashes) >= self.max_cache_size:
            old_hash = self.seen_hashes[0]
            self.seen_set.discard(old_hash)
            self._occurrences.pop(old_hash, None)

        occurrence = Occurrence()
        self.seen_hashes.append(line_hash)
        self.seen_set.add(line_hash)
        self._occurrences[line_hash] = occurrence
        self.stats["unique"] += 1
        return False, occurrence

    def deduplicate_lines(self, lines: Iterable[str]) -> Iterator[str]:
        """Deduplicate a stream of lines."""
        for line in lines:
            if not self.is_duplicate(line):
                yield line

    def deduplicate_counted(self, lines: Iterable[str]) -> Iterator[tuple[str, Occurrence]]:
        """Deduplicate a stream, pairing each kept line with its ``Occurrence``."""
        for line in lines:
            duplicate, occurrence = self._observe(line)
            if not duplicate:
                yield line, occurrence
