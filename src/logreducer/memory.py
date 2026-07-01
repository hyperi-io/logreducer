"""
Memory management and monitoring utilities
"""

import gc
import os
import random
from collections import deque
from collections.abc import Iterable, Iterator
from typing import Any

import psutil


class MemoryMonitor:
    """Monitor and control memory usage during processing"""

    def __init__(self, max_memory_gb: float = 2.0):
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
        """Check current memory usage"""
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
        """Get current memory usage in GB"""
        current = self.process.memory_info().rss
        # Update peak usage
        if current > self.peak_usage_bytes:
            self.peak_usage_bytes = current
        return float(current / (1024**3))

    def get_peak_usage_gb(self) -> float:
        """Get peak memory usage in GB"""
        # Update current peak if needed
        current = self.process.memory_info().rss
        if current > self.peak_usage_bytes:
            self.peak_usage_bytes = current
        return self.peak_usage_bytes / (1024**3)

    def is_limit_exceeded(self) -> bool:
        """Check if memory limit is exceeded"""
        current = self.process.memory_info().rss
        return bool(current > self.effective_limit)

    def reset(self) -> None:
        """Reset peak memory tracking"""
        current_usage = self.process.memory_info().rss
        self.peak_usage_bytes = current_usage

    def estimate_file_strategy(self, file_size_bytes: int) -> str:
        """Determine processing strategy"""
        file_size_gb = file_size_bytes / (1024**3)

        if file_size_gb < self.max_memory_gb * 0.2:
            return "full"
        elif file_size_gb < self.max_memory_gb * 5:
            return "chunked"
        else:
            return "sampled"


class StreamingProcessor:
    """Process large files with constant memory usage"""

    def __init__(self, memory_monitor: MemoryMonitor):
        self.memory_monitor = memory_monitor
        self.chunk_size = memory_monitor.safe_chunk_size

    def read_file_streaming(self, file_path: str) -> Iterator[str]:
        """Read file with minimal memory usage"""
        file_size = os.path.getsize(file_path)
        strategy = self.memory_monitor.estimate_file_strategy(file_size)

        if strategy == "full":
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        yield line

        elif strategy == "chunked":
            yield from self._read_chunked(file_path)

        else:  # sampled
            yield from self._read_sampled(file_path)

    def _read_chunked(self, file_path: str) -> Iterator[str]:
        """Read file in chunks"""
        chunk = []

        with open(file_path, encoding="utf-8", errors="ignore") as f:
            for line_num, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue

                chunk.append(line)

                if len(chunk) >= self.chunk_size:
                    yield from chunk
                    chunk = []

                    if line_num % 100000 == 0:
                        current_gb, is_safe = self.memory_monitor.check_memory()
                        if not is_safe:
                            yield from self._read_sampled_remainder(f)
                            return

            if chunk:
                yield from chunk

    def _read_sampled(self, file_path: str) -> Iterator[str]:
        """Reservoir sampling for huge files (uniform, reproducible).

        Uses Algorithm L with a fixed-seed RNG so every pass over this
        re-iterable FileSource yields the SAME sample - the reducer's multi-pass
        modes need a stable input. (The old ``hash(line) % (i+1)`` reservoir was
        neither uniform nor stable across processes.)
        """
        from .sampling import reservoir_sample

        reservoir_size = min(self.chunk_size, 100000)

        def _lines() -> Iterator[str]:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    stripped = line.strip()
                    if stripped:
                        yield stripped

        yield from reservoir_sample(_lines(), reservoir_size, random.Random(0))

    def _read_sampled_remainder(self, file_handle: Any) -> Iterator[str]:
        """Reservoir-sample the rest of an already-open file (mid-chunk fallback)."""
        from .sampling import reservoir_sample

        def _lines() -> Iterator[str]:
            for line in file_handle:
                stripped = line.strip()
                if stripped:
                    yield stripped

        yield from reservoir_sample(_lines(), 10000, random.Random(0))


class BoundedDeduplicator:
    """Memory-bounded deduplication"""

    def __init__(self, max_cache_size: int = 100000, hash_algorithm: str = "xxhash"):
        self.max_cache_size = max_cache_size

        # Choose hash function
        if hash_algorithm == "xxhash":
            try:
                import xxhash

                self.hash_func = lambda x: xxhash.xxh64(x.encode()).hexdigest()
            except ImportError:
                import hashlib

                self.hash_func = lambda x: hashlib.blake2b(x.encode(), digest_size=16).hexdigest()
        else:
            import hashlib

            self.hash_func = lambda x: hashlib.md5(x.encode(), usedforsecurity=False).hexdigest()

        self.seen_hashes: deque[str] = deque(maxlen=max_cache_size)
        self.seen_set: set[str] = set()
        self.stats = {"total": 0, "unique": 0, "duplicates": 0}

    def is_duplicate(self, line: str) -> bool:
        """Check if line is duplicate"""
        self.stats["total"] += 1
        line_hash = self.hash_func(line)

        if line_hash in self.seen_set:
            self.stats["duplicates"] += 1
            return True

        if len(self.seen_hashes) >= self.max_cache_size:
            old_hash = self.seen_hashes[0]
            self.seen_set.discard(old_hash)

        self.seen_hashes.append(line_hash)
        self.seen_set.add(line_hash)
        self.stats["unique"] += 1
        return False

    def deduplicate_lines(self, lines: Iterable[str]) -> Iterator[str]:
        """Deduplicate a stream of lines"""
        for line in lines:
            if not self.is_duplicate(line):
                yield line
