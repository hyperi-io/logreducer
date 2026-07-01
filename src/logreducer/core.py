"""
Core LogReducer implementation
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .logging_config import get_logger, setup_logging

# Optional import for progress bars
try:
    from tqdm import tqdm  # type: ignore[import-untyped]

    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

    # Fallback - no-op tqdm
    def tqdm(x: Any, **kwargs: Any) -> Any:
        return x


from .anomaly import AnomalyDetector
from .config import ProcessingLevel, ProcessingMode, get_preset_config
from .memory import BoundedDeduplicator, MemoryMonitor, StreamingProcessor
from .patterns import FuzzyDeduplicator, PatternExtractor
from .temporal import TemporalProcessor


class LogReducer:
    """
    Main log reduction class

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
        **kwargs: Any,
    ) -> None:
        """
        Initialize LogReducer

        Args:
            level: Processing level (standard/enhanced/maximum)
            mode: Processing mode (pattern/anomaly/temporal/hybrid)
            max_memory_gb: Memory limit override
            max_patterns: Maximum patterns override
            **kwargs: Additional config overrides
        """
        # Parse level and mode
        if isinstance(level, str):
            level = ProcessingLevel(level.lower())
        if isinstance(mode, str):
            mode = ProcessingMode(mode.lower())

        self.level = level
        self.mode = mode

        # Get base config
        self.config = get_preset_config(level)

        # Apply overrides BEFORE setting up logging
        if max_memory_gb:
            self.config.max_memory_gb = max_memory_gb
        if max_patterns:
            self.config.max_patterns = max_patterns

        for key, value in kwargs.items():
            if hasattr(self.config, key):
                # Special handling for output_format to convert string to enum
                if key == "output_format" and isinstance(value, str):
                    from .config import OutputFormat

                    value = OutputFormat(value.lower())
                setattr(self.config, key, value)

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
        self.streaming_processor = StreamingProcessor(self.memory_monitor)
        self.deduplicator = BoundedDeduplicator(self.config.dedup_cache_size, self.config.hash_algorithm)
        self.pattern_extractor = PatternExtractor(self.config)

        if self.config.fuzzy_threshold and self.level != ProcessingLevel.STANDARD:
            self.fuzzy_dedup: FuzzyDeduplicator | None = FuzzyDeduplicator(self.config.fuzzy_threshold)
        else:
            self.fuzzy_dedup = None

        if mode in [ProcessingMode.TEMPORAL, ProcessingMode.HYBRID]:
            self.temporal_processor: TemporalProcessor | None = TemporalProcessor(self.config.temporal_window_minutes)
        else:
            self.temporal_processor = None

        if mode in [ProcessingMode.ANOMALY, ProcessingMode.HYBRID]:
            self.anomaly_detector: AnomalyDetector | None = AnomalyDetector(self.config.anomaly_contamination)
        else:
            self.anomaly_detector = None

        self.stats: dict[str, Any] = {}

    def process_file(
        self,
        input_file: str,
        output_file: str | None = None,
        return_metadata: bool = False,
    ) -> list[str] | dict:
        """
        Process log file and reduce to representative samples

        Args:
            input_file: Path to input log file
            output_file: Optional output file path
            return_metadata: Return metadata dict instead of just lines

        Returns:
            List of reduced log lines or dict with lines and metadata
        """
        start_time = time.time()

        # Check file
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"File not found: {input_file}")

        file_size = os.path.getsize(input_file)
        file_size_mb = file_size / (1024 * 1024)

        if self.config.enable_logging:
            self.logger.info(f"Processing {input_file} ({file_size_mb:.1f} MB)")
            self.logger.info(f"Mode: {self.mode.value}, Level: {self.level.value}")
            self.logger.info(f"Memory limit: {self.config.max_memory_gb:.1f} GB")

        # Count input lines for proper reduction calculation
        with open(input_file, encoding="utf-8", errors="ignore") as f:
            input_lines = sum(1 for _ in f)

        # Process based on mode
        if self.mode == ProcessingMode.PATTERN:
            result_lines = self._process_pattern_mode(input_file)
        elif self.mode == ProcessingMode.ANOMALY:
            result_lines = self._process_anomaly_mode(input_file)
        elif self.mode == ProcessingMode.TEMPORAL:
            result_lines = self._process_temporal_mode(input_file)
        else:  # HYBRID
            result_lines = self._process_hybrid_mode(input_file)

        # Calculate stats
        processing_time = time.time() - start_time
        output_lines = len(result_lines)
        reduction_percent = (1 - output_lines / max(input_lines, 1)) * 100 if input_lines > 0 else 0

        self.stats = {
            "input_file": str(input_file),  # Convert to string for JSON serialization
            "input_lines": input_lines,
            "input_size_mb": file_size_mb,
            "output_lines": output_lines,
            "reduction_percent": reduction_percent,
            "processing_time_seconds": processing_time,
            "processing_rate_mb_per_sec": file_size_mb / max(processing_time, 0.001),
            "mode": self.mode.value,
            "level": self.level.value,
            "memory_limit_gb": self.config.max_memory_gb,
        }

        # Save output
        if output_file:
            self._save_output(result_lines, output_file)

        # Print summary
        self._print_summary()

        if return_metadata:
            return {
                "lines": result_lines,
                "stats": self.stats,
                "config": vars(self.config),
            }
        else:
            return result_lines

    def _process_pattern_mode(self, input_file: str) -> list[str]:
        """Process using pattern extraction"""
        if self.config.enable_logging:
            self.logger.info("Phase 1/3: Reading and deduplicating")

        # Stream read with deduplication
        lines = self.streaming_processor.read_file_streaming(input_file)
        unique_lines = list(self.deduplicator.deduplicate_lines(lines))

        if self.config.enable_logging:
            self.logger.info(f"Unique lines: {len(unique_lines):,}")

        # Fuzzy deduplication if enabled
        if self.fuzzy_dedup and self.level != ProcessingLevel.STANDARD:
            if self.config.enable_logging:
                self.logger.info("Phase 2/3: Fuzzy deduplication")
            unique_lines = self.fuzzy_dedup.deduplicate(unique_lines)
            if self.config.enable_logging:
                self.logger.info(f"After fuzzy dedup: {len(unique_lines):,}")

        # Pattern extraction
        if self.config.enable_logging:
            self.logger.info("Phase 3/3: Pattern extraction")
        patterns = self.pattern_extractor.extract_patterns(unique_lines)

        # Collect examples
        result = []
        for pattern in patterns[: self.config.max_patterns]:
            result.extend(pattern.examples)

        return result

    def _process_anomaly_mode(self, input_file: str) -> list[str]:
        """Process using anomaly detection"""
        if not self.anomaly_detector:
            if self.config.enable_logging:
                self.logger.warning("Anomaly detector not available, falling back to pattern mode")
            return self._process_pattern_mode(input_file)

        if self.config.enable_logging:
            self.logger.info("Phase 1/2: Reading and deduplicating")
        lines = self.streaming_processor.read_file_streaming(input_file)
        unique_lines = list(self.deduplicator.deduplicate_lines(lines))

        if self.config.enable_logging:
            self.logger.info("Phase 2/2: Anomaly detection")
        anomalous, normal = self.anomaly_detector.detect_anomalies(unique_lines)

        # Keep all anomalies + sample of normal
        result = anomalous[: self.config.max_patterns // 2]

        # Add some normal for context
        normal_sample_size = min(len(normal), self.config.max_patterns // 4)
        if normal_sample_size > 0:
            import secrets

            # Use cryptographically secure random sampling
            secure_random = secrets.SystemRandom()
            result.extend(secure_random.sample(normal, normal_sample_size))

        return result

    def _process_temporal_mode(self, input_file: str) -> list[str]:
        """Process using temporal analysis"""
        if not self.temporal_processor:
            if self.config.enable_logging:
                self.logger.warning("Temporal processor not available, falling back to pattern mode")
            return self._process_pattern_mode(input_file)

        if self.config.enable_logging:
            self.logger.info("Phase 1/2: Reading lines")
        lines = list(self.streaming_processor.read_file_streaming(input_file))

        if self.config.enable_logging:
            self.logger.info("Phase 2/2: Temporal processing")
        temporal_results = self.temporal_processor.process_temporal(lines)

        # Collect examples from temporal patterns
        result = []
        for pattern in temporal_results.get("temporal_patterns", [])[: self.config.max_patterns]:
            if "example" in pattern:
                result.append(pattern["example"])

        for pattern in temporal_results.get("timeless_patterns", [])[:100]:
            if "example" in pattern:
                result.append(pattern["example"])

        return result

    def _process_hybrid_mode(self, input_file: str) -> list[str]:
        """Process using combined approach"""
        if self.config.enable_logging:
            self.logger.info("Hybrid mode: combining pattern and anomaly detection")

        # Get patterns
        pattern_lines = self._process_pattern_mode(input_file)

        # Get anomalies if available
        if self.anomaly_detector:
            lines = list(self.streaming_processor.read_file_streaming(input_file))
            unique_lines = list(self.deduplicator.deduplicate_lines(lines))
            anomalous, _ = self.anomaly_detector.detect_anomalies(unique_lines)

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

    def _save_output(self, lines: list[str], output_file: str) -> None:
        """Save output to file in specified format"""
        from .config import OutputFormat

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Save in requested format
        if self.config.output_format == OutputFormat.JSON:
            # Full JSON format with metadata
            output_data = {
                "lines": lines,
                "stats": self.stats,
                "config": {
                    k: str(v) if hasattr(v, "value") else v
                    for k, v in vars(self.config).items()
                    if not k.startswith("_")
                },
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
            with open(meta_file, "w") as f:
                json.dump(
                    {
                        "stats": self.stats,
                        "config": {
                            k: str(v) if hasattr(v, "value") else v
                            for k, v in vars(self.config).items()
                            if not k.startswith("_")
                        },
                        "timestamp": datetime.now().isoformat(),
                    },
                    f,
                    indent=2,
                )

            if self.config.enable_logging:
                self.logger.info(f"Output saved to {output_file}")
                self.logger.info(f"Metadata saved to {meta_file}")

    def _print_summary(self) -> None:
        """Log processing summary"""
        self.logger.info("\n" + "=" * 60)
        self.logger.info("LOG REDUCTION SUMMARY")
        self.logger.info("=" * 60)
        self.logger.info(f"Mode: {self.mode.value}")
        self.logger.info(f"Level: {self.level.value}")
        self.logger.info(f"Input: {self.stats['input_size_mb']:.1f} MB")
        self.logger.info(f"Output: {self.stats['output_lines']} lines")
        self.logger.info(f"Reduction: {self.stats['reduction_percent']:.1f}%")
        self.logger.info(f"Time: {self.stats['processing_time_seconds']:.1f} seconds")
        self.logger.info(f"Rate: {self.stats['processing_rate_mb_per_sec']:.1f} MB/sec")
        self.logger.info("=" * 60)

    def estimate_processing(self, file_path: str) -> dict:
        """Estimate processing requirements before running"""
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
