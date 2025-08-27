"""
LogReducer - High-performance log analysis and reduction system

Enterprise-grade log processing module that intelligently reduces large log files while
preserving critical patterns and anomalies. Features memory-safe streaming, temporal analysis,
and advanced pattern extraction for operational insights.

Copyright (c) HyperSec 2025. All rights reserved.
Licensed under the HyperSec EULA: https://hypersec.io/eula
Author: Derek <noreply@hypersec.io>
"""

__version__ = "3.2.1"
__author__ = "Derek"
__email__ = "noreply@hypersec.io"
__license__ = "HyperSec EULA"
__copyright__ = "Copyright (c) HyperSec 2025"
__description__ = "High-performance log reduction with intelligent pattern extraction and anomaly detection"
__url__ = "https://github.com/hypersec-io/logreducer"

from .core import LogReducer
from .config import ProcessingLevel, ProcessingMode, BigDialConfig, OutputFormat
from .logging_config import setup_logging

__all__ = [
    "LogReducer",
    "ProcessingLevel",
    "ProcessingMode",
    "BigDialConfig",
    "OutputFormat",
    "setup_logging",
    "__version__",
    "__author__",
    "__email__",
    "__license__",
    "__description__",
    "__url__",
]

# Type annotation for mypy
py_typed = True
