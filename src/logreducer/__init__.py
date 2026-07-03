"""LogReducer - reduce large volumes of log lines to a representative sample.

A streaming reduction engine (dedup -> pattern mining -> anomaly/temporal
analysis) with an IO-agnostic core: any re-iterable stream of str lines is a
valid Source. Ships as both a library and a `logreducer` CLI.

Copyright 2026 HYPERI PTY LIMITED.
Licensed under the Apache License, Version 2.0 (see LICENSE).
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("logreducer")
except PackageNotFoundError:  # running from a source tree that is not installed
    __version__ = "0.0.0+unknown"

from .config import BigDialConfig, OutputFormat, ProcessingLevel, ProcessingMode
from .core import LogReducer
from .logging_config import setup_logging
from .sampling import SamplingNotSupported
from .sinks import FileSink, Sink
from .sources import FileSource, Source
from .target import reduce_to_target

__all__ = [
    "BigDialConfig",
    "FileSink",
    "FileSource",
    "LogReducer",
    "OutputFormat",
    "ProcessingLevel",
    "ProcessingMode",
    "SamplingNotSupported",
    "Sink",
    "Source",
    "__version__",
    "reduce_to_target",
    "setup_logging",
]
