"""
Configuration and tuning parameters for LogReducer

This module provides configurable security levels and processing settings.
"""

import multiprocessing as mp
from dataclasses import dataclass
from enum import Enum

import psutil


class ProcessingLevel(Enum):
    """Processing level determines speed/quality tradeoff"""

    STANDARD = "standard"  # Fast, 99% reduction
    ENHANCED = "enhanced"  # Balanced, 99.5% reduction
    MAXIMUM = "maximum"  # Thorough, 99.9% reduction


class ProcessingMode(Enum):
    """Processing mode determines reduction strategy"""

    PATTERN = "pattern"  # Pattern-based reduction (Drain3)
    ANOMALY = "anomaly"  # Anomaly detection focus
    TEMPORAL = "temporal"  # Time-based sampling
    HYBRID = "hybrid"  # Combined approach


class OutputFormat(Enum):
    """Output format for reduced logs"""

    LINE = "line"  # Line-by-line text output (default)
    JSON = "json"  # JSON structured output
    JSONL = "jsonl"  # JSON Lines format (one JSON per line)


@dataclass
class BigDialConfig:
    """Big dial tuning parameters"""

    # Memory Control
    max_memory_gb: float = 2.0
    chunk_size: int = 50000
    dedup_cache_size: int = 100000

    # Speed Control
    n_workers: int = None
    hash_algorithm: str = "xxhash"
    use_polars: bool = True
    single_pass: bool = True

    # Quality Control
    drain_similarity: float = 0.4
    fuzzy_threshold: float = 0.8
    min_pattern_occurrences: int = 2
    anomaly_contamination: float = 0.1

    # Temporal Control
    temporal_window_minutes: int = 60
    preserve_burst_patterns: bool = True

    # Sampling Control
    reservoir_size: int = 100000
    progressive_sampling: bool = True
    max_patterns: int = 1000
    examples_per_pattern: int = 3

    # Logging Control
    enable_logging: bool = False  # Logging disabled by default
    log_file: str = None  # Path to log file (None = no file logging)
    log_level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR
    log_format: str = "rfc3339"  # rfc3339 or simple

    # Output Control
    output_format: OutputFormat = OutputFormat.LINE  # Default line-by-line
    pretty_json: bool = False  # Pretty print JSON output

    def __post_init__(self) -> None:
        if self.n_workers is None:
            # Auto-detect CPU cores, especially important in containers
            cpu_count = mp.cpu_count()
            # In containers, respect CPU limits if available
            try:
                # Try to read container CPU quota (Docker/Kubernetes)
                with open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us", "r") as f:
                    quota = int(f.read().strip())
                with open("/sys/fs/cgroup/cpu/cpu.cfs_period_us", "r") as f:
                    period = int(f.read().strip())
                if quota > 0 and period > 0:
                    container_cpus = max(1, int(quota / period))
                    cpu_count = min(cpu_count, container_cpus)
            except (FileNotFoundError, ValueError, IOError):
                # Not in a container or cgroup not available, use system CPU count
                pass

            # Set n_workers to CPU count (no arbitrary limit)
            self.n_workers = cpu_count

        available_gb = psutil.virtual_memory().available / (1024**3)
        if self.max_memory_gb > available_gb * 0.7:
            self.max_memory_gb = available_gb * 0.7


def get_preset_config(level: ProcessingLevel) -> BigDialConfig:
    """Get preset configuration for processing level"""
    if level == ProcessingLevel.STANDARD:
        return BigDialConfig(
            max_memory_gb=1.0,
            chunk_size=100000,
            dedup_cache_size=50000,
            drain_similarity=0.5,
            fuzzy_threshold=None,  # Disabled for speed
            max_patterns=500,
            examples_per_pattern=2,
        )
    elif level == ProcessingLevel.ENHANCED:
        return BigDialConfig(
            max_memory_gb=2.0,
            chunk_size=50000,
            dedup_cache_size=100000,
            drain_similarity=0.4,
            fuzzy_threshold=0.8,
            max_patterns=1000,
            examples_per_pattern=3,
        )
    else:  # MAXIMUM
        return BigDialConfig(
            max_memory_gb=4.0,
            chunk_size=25000,
            dedup_cache_size=200000,
            drain_similarity=0.3,
            fuzzy_threshold=0.9,
            max_patterns=2000,
            examples_per_pattern=5,
        )
