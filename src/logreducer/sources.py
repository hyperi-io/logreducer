"""Input sources for logreducer.

logreducer is a pure reduction engine over an abstraction: its input is any
RE-ITERABLE iterable of ``str`` lines - a "source". ``__iter__`` must return a
FRESH iterator each call, because some reduction modes make more than one pass
over the input (hybrid reads it twice). A ``list[str]``, or a class whose
``__iter__`` re-opens the underlying stream, satisfies this; a bare generator
does not.

The package does not own connections or the loading path. An application can
hand the reducer its own iterable - a database cursor, a Kafka consumer, an
open file - and the reducer never manages that IO. The adapters here are thin
conveniences for the CLI and quick use: ``FileSource`` is built in; SQL /
ClickHouse / Kafka sources live behind optional extras (see the sql, clickhouse
and kafka submodules).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Protocol, runtime_checkable

from .memory import MemoryMonitor, StreamingProcessor


@runtime_checkable
class Source(Protocol):
    """A re-iterable stream of log lines.

    Any object whose ``__iter__`` yields ``str`` and can be iterated more than
    once is a valid source - a plain ``list[str]`` included.
    """

    def __iter__(self) -> Iterator[str]: ...


class FileSource:
    """Stream stripped, non-empty lines from a text file.

    Re-iterable and memory-aware: each iteration re-opens the file and streams
    it through the constant-memory strategy (full / chunked / reservoir-sampled
    by size), so the reducer can make multiple passes without loading the file.
    """

    def __init__(self, path: str | os.PathLike[str], *, max_memory_gb: float = 2.0) -> None:
        self.path = os.fspath(path)
        self._processor = StreamingProcessor(MemoryMonitor(max_memory_gb))

    def __iter__(self) -> Iterator[str]:
        return self._processor.read_file_streaming(self.path)

    @property
    def size_bytes(self) -> int | None:
        """File size in bytes, or None if it cannot be determined."""
        try:
            return os.path.getsize(self.path)
        except OSError:
            return None

    def __repr__(self) -> str:
        return f"FileSource({self.path!r})"
