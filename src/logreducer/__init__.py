"""
LogReducer - High-performance log analysis and reduction system

Enterprise-grade log processing module that intelligently reduces large log files while
preserving critical patterns and anomalies. Features memory-safe streaming, temporal analysis,
and advanced pattern extraction for operational insights.

Copyright 2026 HYPERI PTY LIMITED.
Licensed under the Apache License, Version 2.0 (see LICENSE).
Author: Derek <noreply@hyperi.io>
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("logreducer")
except PackageNotFoundError:  # running from a source tree that is not installed
    __version__ = "0.0.0+unknown"

__author__ = "Derek"
__email__ = "noreply@hyperi.io"
__license__ = "Apache-2.0"
__copyright__ = "Copyright 2026 HYPERI PTY LIMITED"
__description__ = "High-performance log reduction with intelligent pattern extraction and anomaly detection"
__url__ = "https://github.com/hyperi-io/logreducer"

from .config import BigDialConfig, OutputFormat, ProcessingLevel, ProcessingMode
from .core import LogReducer
from .logging_config import setup_logging

__all__ = [
    "BigDialConfig",
    "LogReducer",
    "OutputFormat",
    "ProcessingLevel",
    "ProcessingMode",
    "__author__",
    "__description__",
    "__email__",
    "__license__",
    "__url__",
    "__version__",
    "setup_logging",
]

# Type annotation for mypy
py_typed = True
