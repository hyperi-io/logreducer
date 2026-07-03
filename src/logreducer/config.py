"""Configuration and tuning parameters for LogReducer."""

import os
import types
import typing
from dataclasses import dataclass, fields
from enum import Enum

import psutil
from loguru import logger


class ProcessingLevel(Enum):
    """Processing level determines speed/quality tradeoff."""

    STANDARD = "standard"  # Fast, 99% reduction
    ENHANCED = "enhanced"  # Balanced, 99.5% reduction
    MAXIMUM = "maximum"  # Thorough, 99.9% reduction


class ProcessingMode(Enum):
    """Processing mode determines reduction strategy."""

    PATTERN = "pattern"  # Pattern-based reduction (Drain3)
    ANOMALY = "anomaly"  # Anomaly detection focus
    TEMPORAL = "temporal"  # Time-based sampling
    HYBRID = "hybrid"  # Combined approach


class OutputFormat(Enum):
    """Output format for reduced logs."""

    LINE = "line"  # Line-by-line text output (default)
    JSON = "json"  # JSON structured output
    JSONL = "jsonl"  # JSON Lines format (one JSON per line)


@dataclass
class BigDialConfig:
    """Big dial tuning parameters."""

    # Memory Control. The engine streams, so this cap mainly sizes the file
    # read strategy (full/chunked/sampled), the reservoir, and the watchdog -
    # measured reductions use tens of MB, so the default is deliberately low
    # and container-friendly.
    max_memory_gb: float = 1.0
    dedup_cache_size: int = 100000

    # Speed Control
    hash_algorithm: str = "xxhash"

    # Quality Control
    drain_similarity: float = 0.4
    fuzzy_threshold: float | None = 0.8
    min_pattern_occurrences: int = 2
    anomaly_contamination: float = 0.1
    # Bound the Drain3 template store (LRU-evict beyond this many templates).
    # None = unbounded (default; the store grows with distinct templates).
    max_clusters: int | None = None
    # Cap the rows fed to anomaly detection (reservoir-sampled). Bounds the
    # TF-IDF matrix on a huge unique-line set, at the cost of anomaly recall
    # (rare lines may be sampled out). None = no cap (use every unique line).
    anomaly_max_rows: int | None = None

    # Temporal Control
    temporal_window_minutes: int = 60

    # Sampling Control
    max_patterns: int = 1000
    examples_per_pattern: int = 3

    # Logging Control
    enable_logging: bool = False  # Logging disabled by default
    log_file: str | None = None  # Path to log file (None = no file logging)
    log_level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR
    log_format: str = "rfc3339"  # rfc3339 or simple

    # Output Control
    output_format: OutputFormat = OutputFormat.LINE  # Default line-by-line
    pretty_json: bool = False  # Pretty print JSON output

    def __post_init__(self) -> None:
        # Never promise more memory than the host can give: clamp to 70% of
        # what is currently available, and say so rather than silently mutate.
        available_gb = psutil.virtual_memory().available / (1024**3)
        if self.max_memory_gb > available_gb * 0.7:
            clamped = available_gb * 0.7
            logger.warning(
                f"max_memory_gb={self.max_memory_gb:.1f} exceeds 70% of available RAM; clamped to {clamped:.1f} GB"
            )
            self.max_memory_gb = clamped

    @classmethod
    def from_env(cls, *prefixes: str) -> "BigDialConfig":
        """Build a config from environment variables, cascade-aware.

        ``from_env()`` reads ``LOGREDUCER_<FIELD>`` (upper-cased field names,
        e.g. ``LOGREDUCER_MAX_MEMORY_GB=0.5``). Pass explicit prefixes to
        cascade: ``from_env("DFE", "LOGREDUCER")`` reads ``DFE_<FIELD>`` first,
        then falls back to ``LOGREDUCER_<FIELD>`` - the same
        prefixed-overrides-bare convention as the host-app config cascades this
        is designed to slot under. Unset fields keep their dataclass defaults,
        so a host can drive only the knobs it cares about.
        """
        if not prefixes:
            prefixes = ("LOGREDUCER",)
        overrides: dict[str, object] = {}
        for field in fields(cls):
            for prefix in prefixes:
                raw = os.environ.get(f"{prefix.rstrip('_')}_{field.name.upper()}")
                if raw is not None:
                    overrides[field.name] = _coerce_env_value(raw, field.name)
                    break
        return cls(**overrides)  # type: ignore[arg-type]


def _coerce_env_value(raw: str, field_name: str) -> object:
    """Coerce an env string to the annotated type of a BigDialConfig field."""
    hints = typing.get_type_hints(BigDialConfig)
    target = hints[field_name]
    # Unwrap Optional[X]: 'none'/'null'/'' mean None, otherwise coerce to X.
    if isinstance(target, types.UnionType):
        args = [a for a in typing.get_args(target) if a is not type(None)]
        if raw.strip().lower() in ("", "none", "null"):
            return None
        target = args[0]
    if target is bool:
        return raw.strip().lower() in ("1", "true", "yes", "on")
    if target is int:
        return int(raw)
    if target is float:
        return float(raw)
    if target is OutputFormat:
        return OutputFormat(raw.strip().lower())
    return raw


def get_preset_config(level: ProcessingLevel) -> BigDialConfig:
    """Get preset configuration for processing level."""
    if level == ProcessingLevel.STANDARD:
        return BigDialConfig(
            max_memory_gb=0.5,
            dedup_cache_size=50000,
            drain_similarity=0.5,
            fuzzy_threshold=None,  # Disabled for speed
            max_patterns=500,
            examples_per_pattern=2,
        )
    elif level == ProcessingLevel.ENHANCED:
        return BigDialConfig(
            max_memory_gb=1.0,
            dedup_cache_size=100000,
            drain_similarity=0.4,
            fuzzy_threshold=0.8,
            max_patterns=1000,
            examples_per_pattern=3,
        )
    else:  # MAXIMUM
        return BigDialConfig(
            max_memory_gb=2.0,
            dedup_cache_size=200000,
            drain_similarity=0.3,
            fuzzy_threshold=0.9,
            max_patterns=2000,
            examples_per_pattern=5,
        )
