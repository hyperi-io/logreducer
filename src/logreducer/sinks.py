"""Output sinks for logreducer.

The reduction engine returns its result in memory (a ``list[str]``) - that is
the primary, dependency-free output. A *sink* is the abstraction for sending
those reduced lines somewhere else: a file, a Kafka topic, a database. Like
``Source`` on the input side, a sink is a thin seam - the package does not own
the connection or the delivery guarantees; an application can pass its own.

``Sink`` is a structural protocol: anything with a ``write(lines) -> int`` is a
sink. ``FileSink`` is built in; the Kafka producer sink lives behind the
``kafka`` optional extra (see the kafka submodule).
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class Sink(Protocol):
    """A destination for reduced log lines.

    ``write`` consumes an iterable of ``str`` lines and returns the number of
    lines written. It may be called with a generator, so implementations should
    iterate lazily rather than materialising the whole batch.
    """

    def write(self, lines: Iterable[str]) -> int: ...


class FileSink:
    """Write reduced lines to a text file in one of three formats.

    A standalone, format-aware writer (``line`` / ``json`` / ``jsonl``) that an
    application can use without touching the reducer. It streams the ``line``
    and ``jsonl`` formats a row at a time (constant memory); ``json`` buffers
    the list because the format is a single document.

    This is deliberately simpler than the reducer's own ``output_file`` path,
    which additionally writes a ``.meta.json`` sidecar of run stats - that needs
    the reducer's context, whereas a sink only sees the lines.
    """

    def __init__(self, path: str | os.PathLike[str], *, output_format: str = "line") -> None:
        self.path = os.fspath(path)
        fmt = output_format.lower()
        if fmt not in ("line", "json", "jsonl"):
            raise ValueError(f"Unknown output_format {output_format!r} (use line, json or jsonl)")
        self.output_format = fmt

    def write(self, lines: Iterable[str]) -> int:
        output_path = Path(self.path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        count = 0
        if self.output_format == "json":
            # A JSON document is a single value - the list has to be built.
            materialised = list(lines)
            count = len(materialised)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump({"lines": materialised, "timestamp": datetime.now().isoformat()}, f, indent=2)
        elif self.output_format == "jsonl":
            with open(output_path, "w", encoding="utf-8") as f:
                for line in lines:
                    json.dump({"line": line}, f)
                    f.write("\n")
                    count += 1
        else:  # line
            with open(output_path, "w", encoding="utf-8") as f:
                for line in lines:
                    f.write(line + "\n")
                    count += 1
        return count

    def __repr__(self) -> str:
        return f"FileSink({self.path!r}, output_format={self.output_format!r})"
