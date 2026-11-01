"""Core LogReducer implementation."""

import json
import os
import random
import time
from collections.abc import Iterable
from dataclasses import replace
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal, overload

from .anomaly import AnomalyDetector
from .config import BigDialConfig, OutputFormat, ProcessingLevel, ProcessingMode, get_preset_config
from .logging_config import get_logger, setup_logging
from .memory import BoundedDeduplicator, MemoryMonitor
from .patterns import FuzzyDeduplicator, PatternExtractor, SevereShapes, is_severe, pattern_priority
from .sampling import reservoir_sample
from .sinks import Sink
from .sources import FileSource, Source
from .temporal import TemporalProcessor


class LogReducer:
    """Main log reduction class.

    Example:
        reducer = LogReducer(level="enhanced")
        reduced = reducer.process_file("app.log")
    """

    def __init__(
        self,
        level: str | ProcessingLevel = "standard",
        mode: str | ProcessingMode = "pattern",
        max_memory_gb: float | None = None,
        max_patterns: int | None = None,
        config: BigDialConfig | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize LogReducer.

        Args:
            level: Processing level (standard/enhanced/maximum)
            mode: Processing mode (pattern/anomaly/temporal/hybrid)
            max_memory_gb: Memory limit override
            max_patterns: Maximum patterns override
            config: A fully-built BigDialConfig to use INSTEAD of the level
                preset - the injection seam for a host application that owns
                its own config cascade (build the config however you like and
                hand it over; kwargs still apply on top). Copied, so the
                caller's object is never mutated. ``level`` then only selects
                the fuzzy-dedup gate, not preset values.
            **kwargs: Additional config overrides
        """
        # Parse level and mode
        if isinstance(level, str):
            level = ProcessingLevel(level.lower())
        if isinstance(mode, str):
            mode = ProcessingMode(mode.lower())

        self.level = level
        self.mode = mode

        # Base config: an injected one wins over the level preset.
        base = config if config is not None else get_preset_config(level)

        overrides: dict[str, Any] = {}
        if max_memory_gb is not None:
            overrides["max_memory_gb"] = max_memory_gb
        if max_patterns is not None:
            overrides["max_patterns"] = max_patterns
        for key, value in kwargs.items():
            # Fail fast on typos: silently dropping an unknown override means a
            # user's tuning quietly does nothing.
            if not hasattr(base, key):
                raise ValueError(f"Unknown config option {key!r} (see BigDialConfig for valid fields)")
            if key == "output_format" and isinstance(value, str):
                value = OutputFormat(value.lower())
            overrides[key] = value
        # replace() builds a new config, so overrides are validated and memory-clamped like any other.
        self.config = replace(base, **overrides)

        # Setup logging based on config (after overrides applied)
        setup_logging(
            enable=self.config.enable_logging,
            log_file=self.config.log_file,
            log_level=self.config.log_level,
            log_format=self.config.log_format,
        )

        # Get logger for this module
        self.logger = get_logger("logreducer.core")

        # Initialize components
        self.memory_monitor = MemoryMonitor(self.config.max_memory_gb)

        if mode in [ProcessingMode.ANOMALY, ProcessingMode.HYBRID]:
            self.anomaly_detector: AnomalyDetector | None = AnomalyDetector(self.config.anomaly_contamination)
        else:
            self.anomaly_detector = None

        # Stateful analysis components (dedup seen-set, Drain3 miners, fuzzy
        # LSH) are (re)created per run by _reset_components(), so a reused
        # reducer never carries one run's accumulated state into the next.
        self.fuzzy_dedup: FuzzyDeduplicator | None = None
        self.temporal_processor: TemporalProcessor | None = None
        self._reset_components()

        self.stats: dict[str, Any] = {}

    def _reset_components(self) -> None:
        """Recreate the stateful analysis components for a fresh, isolated run.

        The deduplicator (seen-set), Drain3 miners (pattern AND per-window
        temporal), and fuzzy-dedup LSH all accumulate per-line state.
        Recreating them keeps a LogReducer instance reusable across
        reduce()/process_file() calls, and lets a single run make independent
        deduplication passes (hybrid mode) without the first pass poisoning
        the second.
        """
        self.deduplicator = BoundedDeduplicator(self.config.dedup_cache_size, self.config.hash_algorithm)
        self.pattern_extractor = PatternExtractor(self.config)
        if self.config.fuzzy_threshold and self.level != ProcessingLevel.STANDARD:
            self.fuzzy_dedup = FuzzyDeduplicator(self.config.fuzzy_threshold, self.config.dedup_cache_size)
        else:
            self.fuzzy_dedup = None
        if self.mode in [ProcessingMode.TEMPORAL, ProcessingMode.HYBRID]:
            self.temporal_processor = TemporalProcessor(self.config.temporal_window_minutes)
        else:
            self.temporal_processor = None

    @overload
    def reduce(
        self,
        source: Source,
        output_file: str | None = None,
        return_metadata: Literal[False] = False,
        sink: Sink | None = None,
    ) -> list[str]: ...

    @overload
    def reduce(
        self,
        source: Source,
        output_file: str | None = None,
        *,
        return_metadata: Literal[True],
        sink: Sink | None = None,
    ) -> dict[str, Any]: ...

    @overload
    def reduce(
        self,
        source: Source,
        output_file: str | None = None,
        return_metadata: bool = False,
        sink: Sink | None = None,
    ) -> list[str] | dict[str, Any]: ...

    def reduce(
        self,
        source: Source,
        output_file: str | None = None,
        return_metadata: bool = False,
        sink: Sink | None = None,
    ) -> list[str] | dict[str, Any]:
        """Reduce a source of log lines to a representative sample.

        This is the core entry point: it operates on an abstraction, not on IO.
        The source is any re-iterable stream of str lines - a list, a
        FileSource, or an app-provided iterable wrapping its own DB cursor or
        Kafka consumer. The reducer never manages the connection or loading
        path.

        Args:
            source: Re-iterable stream of str lines (see logreducer.sources).
                Multi-pass modes (hybrid) require the source to be re-iterable.
            output_file: Optional path to also write the result to, with a
                format-aware ``.meta.json`` sidecar of run stats (CLI use).
            return_metadata: Return a dict with lines + stats + config instead
                of just the lines.
            sink: Optional output abstraction (see logreducer.sinks). The
                reduced lines are also handed to ``sink.write`` - a FileSink, a
                KafkaSink, or any app-provided destination.

        Returns:
            The reduced lines in memory (list[str]), or a metadata dict.
        """
        # A Source must be re-iterable: reduce() counts lines in one pass, then
        # re-reads the source to process it (hybrid re-reads again). A one-shot
        # iterator (a bare generator) would be drained by the count and leave
        # nothing to process - fail loudly rather than return an empty result.
        if isinstance(source, str | bytes):
            raise TypeError(
                f"source must be an iterable of lines, got a single {type(source).__name__}; "
                "use process_file() for a path, or pass a list of lines."
            )
        if iter(source) is source:
            raise TypeError(
                "source must be re-iterable (a fresh iterator on each pass); got a "
                "one-shot iterator/generator - wrap it, e.g. list(source)."
            )

        # Fresh analysis state per run: a reused reducer must not carry the
        # previous run's dedup/miner/LSH state, which would drop every line as
        # already-seen and silently return an empty result.
        self._reset_components()

        start_time = time.time()

        # Count input lines for the reduction ratio (one pass over the source).
        # Note: a size-sampled FileSource yields its sampled line count, so for
        # very large files the ratio and input_lines stat are approximate.
        shapes = SevereShapes()
        input_lines = 0
        for line in source:
            input_lines += 1
            shapes.add(line)
        # A FileSource taps its own reads, which see the lines it samples away.
        shapes = getattr(source, "severe_shapes", shapes)

        size_bytes = getattr(source, "size_bytes", None)
        file_size_mb = size_bytes / (1024 * 1024) if size_bytes else None

        if self.config.enable_logging:
            where = f"{file_size_mb:.1f} MB" if file_size_mb is not None else f"{input_lines:,} lines"
            self.logger.info(f"Reducing {source!r} ({where})")
            self.logger.info(f"Mode: {self.mode.value}, Level: {self.level.value}")
            self.logger.info(f"Memory limit: {self.config.max_memory_gb:.1f} GB")

        # Process based on mode
        if self.mode == ProcessingMode.PATTERN:
            result_lines = self._process_pattern_mode(source)
        elif self.mode == ProcessingMode.ANOMALY:
            result_lines = self._process_anomaly_mode(source)
        elif self.mode == ProcessingMode.TEMPORAL:
            result_lines = self._process_temporal_mode(source)
        else:  # HYBRID
            result_lines = self._process_hybrid_mode(source)

        # Modes return quiet lines under their caps. Severe lines are one per shape, outside every
        # cap, so the output is bounded by the caps plus the number of distinct severe shapes.
        result_lines = shapes.lines + result_lines

        # Calculate stats
        processing_time = time.time() - start_time
        output_lines = len(result_lines)
        reduction_percent = (1 - output_lines / max(input_lines, 1)) * 100 if input_lines > 0 else 0
        input_label = getattr(source, "path", None)

        self.stats = {
            "input_file": str(input_label) if input_label is not None else repr(source),
            "input_lines": input_lines,
            "input_size_mb": file_size_mb,
            "output_lines": output_lines,
            "reduction_percent": reduction_percent,
            "processing_time_seconds": processing_time,
            "processing_rate_mb_per_sec": (
                file_size_mb / max(processing_time, 0.001) if file_size_mb is not None else None
            ),
            "mode": self.mode.value,
            "level": self.level.value,
            "memory_limit_gb": self.config.max_memory_gb,
        }

        if output_file:
            self._save_output(result_lines, output_file)

        if sink is not None:
            sink.write(result_lines)

        self._print_summary()

        if return_metadata:
            return {
                "lines": result_lines,
                "stats": self.stats,
                "config": self._config_as_dict(),
            }
        return result_lines

    @overload
    def process_file(
        self,
        input_file: str,
        output_file: str | None = None,
        return_metadata: Literal[False] = False,
    ) -> list[str]: ...

    @overload
    def process_file(
        self,
        input_file: str,
        output_file: str | None = None,
        *,
        return_metadata: Literal[True],
    ) -> dict[str, Any]: ...

    @overload
    def process_file(
        self,
        input_file: str,
        output_file: str | None = None,
        return_metadata: bool = False,
    ) -> list[str] | dict[str, Any]: ...

    def process_file(
        self,
        input_file: str,
        output_file: str | None = None,
        return_metadata: bool = False,
    ) -> list[str] | dict[str, Any]:
        """Reduce a log file - convenience wrapper over reduce() + FileSource.

        Args:
            input_file: Path to the input log file.
            output_file: Optional output file path.
            return_metadata: Return a metadata dict instead of just the lines.

        Returns:
            The reduced lines (list[str]) or a metadata dict.
        """
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"File not found: {input_file}")
        source = FileSource(input_file, max_memory_gb=self.config.max_memory_gb)
        return self.reduce(source, output_file=output_file, return_metadata=return_metadata)

    def _process_pattern_mode(self, source: Source) -> list[str]:
        """Process using pattern extraction, streaming end to end.

        Exact dedup -> optional fuzzy dedup -> Drain3 all run as generators, so
        the unique lines are never collected into a list. Peak memory is the
        bounded dedup cache plus the Drain3 template store (see max_clusters),
        independent of how many unique lines the source has.
        """
        if self.config.enable_logging:
            # One message, not phases: dedup and mining run interleaved as a
            # single generator pipeline, so there is no phase boundary to report.
            self.logger.info("Streaming pipeline: dedup -> fuzzy dedup -> pattern mining")

        quiet_lines = (line for line in source if not is_severe(line))
        unique_stream = self.deduplicator.deduplicate_counted(quiet_lines)
        if self.fuzzy_dedup:
            unique_stream = self.fuzzy_dedup.deduplicate_pairs(unique_stream)
        patterns = self.pattern_extractor.extract_counted_patterns(unique_stream)

        # Collect the examples of quiet patterns (the extractor has already applied max_patterns to
        # them). Severe lines come from the severe shapes that reduce() adds, one per shape.
        result = []
        for pattern in patterns:
            result.extend(line for line in pattern.examples if not is_severe(line))

        return result

    def _cap_for_anomaly(self, unique_lines: Iterable[str]) -> list[str]:
        """Reservoir-cap unique lines to anomaly_max_rows to bound the ML matrix.

        Anomaly detection (Isolation Forest over a TF-IDF matrix) is batch ML and
        cannot stream, so a huge unique-line set is the one place a hard memory
        cap needs an explicit sample. The sample is drawn in one pass over the
        stream, so the full set is never held. Fixed seed = reproducible across
        passes. Trades anomaly recall (a rare line may be sampled out) for bounded
        memory. With no anomaly_max_rows the lines are kept whole.
        """
        cap = self.config.anomaly_max_rows
        if not cap:
            return unique_lines if isinstance(unique_lines, list) else list(unique_lines)
        if isinstance(unique_lines, list) and len(unique_lines) <= cap:
            return unique_lines
        return reservoir_sample(unique_lines, cap, random.Random(0))

    def _detect_quiet_anomalies(self, detector: AnomalyDetector, source: Source) -> tuple[list[str], list[str]]:
        """Return (anomalous, normal) among the quiet unique lines of ``source``.

        Severe lines are left out of the detector's input, since reduce() adds one per shape.
        """
        quiet_unique = (line for line in self.deduplicator.deduplicate_lines(source) if not is_severe(line))
        return detector.detect_anomalies(self._cap_for_anomaly(quiet_unique))

    def _process_anomaly_mode(self, source: Source) -> list[str]:
        """Process using anomaly detection."""
        if not self.anomaly_detector:
            if self.config.enable_logging:
                self.logger.warning("Anomaly detector not available, falling back to pattern mode")
            return self._process_pattern_mode(source)

        if self.config.enable_logging:
            self.logger.info("Reading, deduplicating and anomaly detection")
        anomalous, normal = self._detect_quiet_anomalies(self.anomaly_detector, source)

        # Keep all anomalies (capped) + sample of normal
        result = anomalous[: self.config.max_patterns // 2]

        # Add some normal lines for context. Seeded RNG so a re-run over the
        # same input yields the same sample (consistent with the reproducibility
        # guarantees elsewhere); there is no security requirement here.
        normal_sample_size = min(len(normal), self.config.max_patterns // 4)
        if normal_sample_size > 0:
            result.extend(random.Random(0).sample(normal, normal_sample_size))

        return result

    def _process_temporal_mode(self, source: Source) -> list[str]:
        """Process using temporal analysis."""
        if not self.temporal_processor:
            if self.config.enable_logging:
                self.logger.warning("Temporal processor not available, falling back to pattern mode")
            return self._process_pattern_mode(source)

        if self.config.enable_logging:
            self.logger.info("Phase 1/2: Reading lines")
        # Severe lines never reach the miner: reduce() adds one line per severe shape, not one per window.
        lines = [line for line in source if not is_severe(line)]

        if self.config.enable_logging:
            self.logger.info("Phase 2/2: Temporal processing")
        temporal_results = self.temporal_processor.process_temporal(lines)

        # One example per (window, template), the most important first.
        def rank(patterns: list[dict]) -> list[dict]:
            return sorted(patterns, key=lambda p: pattern_priority(p["template"], p["count"]), reverse=True)

        result = [p["example"] for p in rank(temporal_results["temporal_patterns"])[: self.config.max_patterns]]
        result.extend(p["example"] for p in rank(temporal_results["timeless_patterns"])[:100])

        return result

    def _process_hybrid_mode(self, source: Source) -> list[str]:
        """Process using combined approach."""
        if self.config.enable_logging:
            self.logger.info("Hybrid mode: combining pattern and anomaly detection")

        # Get patterns
        pattern_lines = self._process_pattern_mode(source)

        # Get anomalies if available
        if self.anomaly_detector:
            # The pattern pass above consumed self.deduplicator's seen-set, so the
            # anomaly pass needs a fresh deduplicator - otherwise every line reads
            # as already-seen and no anomalies survive (hybrid -> pattern-only).
            self.deduplicator = BoundedDeduplicator(self.config.dedup_cache_size, self.config.hash_algorithm)
            anomalous, _ = self._detect_quiet_anomalies(self.anomaly_detector, source)

            # Combine, preferring anomalies
            result = anomalous[: self.config.max_patterns // 2]
            result.extend(pattern_lines[: self.config.max_patterns // 2])
        else:
            result = pattern_lines

        # Remove duplicates while preserving order
        seen = set()
        final = []
        for line in result:
            if line not in seen:
                seen.add(line)
                final.append(line)

        return final[: self.config.max_patterns]

    def _config_as_dict(self) -> dict[str, Any]:
        """Config as a JSON-serialisable dict.

        Enum members (output_format, ...) become their ``.value`` string so the
        result survives ``json.dumps`` and never leaks ``OutputFormat.LINE``-style
        reprs into metadata output. Private (``_``-prefixed) attrs are dropped.
        """
        return {
            k: (v.value if isinstance(v, Enum) else v) for k, v in vars(self.config).items() if not k.startswith("_")
        }

    def _save_output(self, lines: list[str], output_file: str) -> None:
        """Save output to file in specified format."""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Save in requested format
        if self.config.output_format == OutputFormat.JSON:
            # Full JSON format with metadata
            output_data = {
                "lines": lines,
                "stats": self.stats,
                "config": self._config_as_dict(),
                "timestamp": datetime.now().isoformat(),
            }
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2 if self.config.pretty_json else None)

            if self.config.enable_logging:
                self.logger.info(f"Output saved to {output_file}")

        elif self.config.output_format == OutputFormat.JSONL:
            # JSON Lines format - one JSON object per line
            with open(output_path, "w", encoding="utf-8") as f:
                for line in lines:
                    json.dump({"line": line, "timestamp": datetime.now().isoformat()}, f)
                    f.write("\n")

            if self.config.enable_logging:
                self.logger.info(f"Output saved to {output_file}")

        else:  # OutputFormat.LINE (default)
            # Traditional line-by-line text output
            with open(output_path, "w", encoding="utf-8") as f:
                for line in lines:
                    f.write(line + "\n")

            # Save metadata separately for line format
            meta_file = output_path.with_suffix(".meta.json")
            with open(meta_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "stats": self.stats,
                        "config": self._config_as_dict(),
                        "timestamp": datetime.now().isoformat(),
                    },
                    f,
                    indent=2,
                )

            if self.config.enable_logging:
                self.logger.info(f"Output saved to {output_file}")
                self.logger.info(f"Metadata saved to {meta_file}")

    def _print_summary(self) -> None:
        """Log processing summary."""
        self.logger.info("\n" + "=" * 60)
        self.logger.info("LOG REDUCTION SUMMARY")
        self.logger.info("=" * 60)
        self.logger.info(f"Mode: {self.mode.value}")
        self.logger.info(f"Level: {self.level.value}")
        # input_size_mb / rate are None for non-file sources (a list, a DB
        # cursor) - only a file has a byte size. Log them when known.
        input_size_mb = self.stats.get("input_size_mb")
        if input_size_mb is not None:
            self.logger.info(f"Input: {input_size_mb:.1f} MB")
        self.logger.info(f"Input lines: {self.stats['input_lines']:,}")
        self.logger.info(f"Output: {self.stats['output_lines']} lines")
        self.logger.info(f"Reduction: {self.stats['reduction_percent']:.1f}%")
        self.logger.info(f"Time: {self.stats['processing_time_seconds']:.1f} seconds")
        rate = self.stats.get("processing_rate_mb_per_sec")
        if rate is not None:
            self.logger.info(f"Rate: {rate:.1f} MB/sec")
        self.logger.info("=" * 60)

    def estimate_processing(self, file_path: str) -> dict:
        """Estimate processing requirements before running."""
        file_size = os.path.getsize(file_path)
        file_size_gb = file_size / (1024**3)

        strategy = self.memory_monitor.estimate_file_strategy(file_size)

        return {
            "file_size_gb": file_size_gb,
            "memory_required_gb": min(file_size_gb * 0.3, self.config.max_memory_gb),
            "strategy": strategy,
            "estimated_time_seconds": file_size_gb * 30,
            "will_sample": strategy == "sampled",
            "estimated_output_lines": min(
                int(file_size_gb * 1000),
                self.config.max_patterns * self.config.examples_per_pattern,
            ),
        }
