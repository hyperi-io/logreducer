"""
Unit tests for core LogReducer functionality
"""

from unittest.mock import Mock, patch

import pytest

from logreducer.config import ProcessingLevel, ProcessingMode
from logreducer.core import LogReducer
from logreducer.sources import FileSource


class TestLogReducerInitialization:
    """Test LogReducer initialization"""

    def test_default_initialization(self):
        """Test LogReducer with default parameters"""
        reducer = LogReducer()

        assert reducer.level == ProcessingLevel.STANDARD
        assert reducer.mode == ProcessingMode.PATTERN
        assert reducer.config.max_memory_gb == 1.0  # Standard preset
        assert reducer.config.max_patterns == 500  # Standard preset

    def test_initialization_with_strings(self):
        """Test LogReducer initialization with string parameters"""
        reducer = LogReducer(level="enhanced", mode="anomaly")

        assert reducer.level == ProcessingLevel.ENHANCED
        assert reducer.mode == ProcessingMode.ANOMALY
        assert reducer.config.max_memory_gb == 2.0  # Enhanced preset

    def test_initialization_with_enums(self):
        """Test LogReducer initialization with enum parameters"""
        reducer = LogReducer(level=ProcessingLevel.MAXIMUM, mode=ProcessingMode.HYBRID)

        assert reducer.level == ProcessingLevel.MAXIMUM
        assert reducer.mode == ProcessingMode.HYBRID
        assert reducer.config.max_memory_gb == 4.0  # Maximum preset

    def test_initialization_with_overrides(self):
        """Test LogReducer initialization with parameter overrides"""
        reducer = LogReducer(level="standard", max_memory_gb=3.0, max_patterns=1500)

        assert reducer.config.max_memory_gb == 3.0  # Override applied
        assert reducer.config.max_patterns == 1500  # Override applied
        # Other standard values should remain
        assert reducer.config.examples_per_pattern == 2

    def test_initialization_with_kwargs(self):
        """Test LogReducer initialization with additional kwargs"""
        reducer = LogReducer(level="enhanced", chunk_size=75000, drain_similarity=0.3)

        assert reducer.config.chunk_size == 75000
        assert reducer.config.drain_similarity == 0.3

    def test_component_initialization(self):
        """Test that all components are properly initialized"""
        reducer = LogReducer(level="enhanced", mode="hybrid")

        # Core components should be initialized. File streaming now lives in
        # FileSource, not on the reducer - the reducer only sees a Source.
        assert reducer.memory_monitor is not None
        assert reducer.deduplicator is not None
        assert reducer.pattern_extractor is not None

        # Mode-specific components
        assert reducer.temporal_processor is not None  # Hybrid includes temporal
        assert reducer.anomaly_detector is not None  # Hybrid includes anomaly

        # Fuzzy dedup should be enabled for enhanced level
        assert reducer.fuzzy_dedup is not None

    def test_standard_level_no_fuzzy_dedup(self):
        """Test that standard level doesn't initialize fuzzy deduplicator"""
        reducer = LogReducer(level="standard")

        assert reducer.fuzzy_dedup is None  # Should be disabled for speed


class TestLogReducerProcessFile:
    """Test LogReducer process_file method"""

    def test_process_file_not_found(self):
        """Test processing non-existent file raises FileNotFoundError"""
        reducer = LogReducer()

        with pytest.raises(FileNotFoundError):
            reducer.process_file("nonexistent_file.log")

    def test_process_file_basic(self, small_log_file):
        """Test basic file processing"""
        reducer = LogReducer(level="standard")

        result = reducer.process_file(str(small_log_file))

        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(line, str) for line in result)

        # Should have stats populated
        assert hasattr(reducer, "stats")
        assert "input_file" in reducer.stats
        assert "output_lines" in reducer.stats
        assert "processing_time_seconds" in reducer.stats

    def test_process_file_with_output(self, small_log_file, test_data_dir):
        """Test file processing with output file"""
        reducer = LogReducer(level="standard")
        output_file = test_data_dir / "output.log"

        result = reducer.process_file(str(small_log_file), str(output_file))

        assert isinstance(result, list)
        assert output_file.exists()

        # Check output file content
        with open(output_file) as f:
            output_lines = [line.strip() for line in f.readlines()]

        assert output_lines == result

        # Metadata file should also exist
        meta_file = output_file.with_suffix(".meta.json")
        assert meta_file.exists()

    def test_process_file_with_metadata(self, small_log_file):
        """Test file processing with metadata return"""
        reducer = LogReducer(level="standard")

        result = reducer.process_file(str(small_log_file), return_metadata=True)

        assert isinstance(result, dict)
        assert "lines" in result
        assert "stats" in result
        assert "config" in result

        assert isinstance(result["lines"], list)
        assert isinstance(result["stats"], dict)
        assert isinstance(result["config"], dict)

        # Verify stats content
        stats = result["stats"]
        assert "input_file" in stats
        assert "output_lines" in stats
        assert "processing_time_seconds" in stats
        assert "mode" in stats
        assert "level" in stats


class TestLogReducerProcessingModes:
    """Test different processing modes"""

    def test_pattern_mode(self, small_log_file):
        """Test pattern processing mode"""
        reducer = LogReducer(mode="pattern", level="standard")

        with patch.object(reducer, "_process_pattern_mode") as mock_process:
            mock_process.return_value = ["test line"]

            result = reducer.process_file(str(small_log_file))

            # process_file wraps the path in a FileSource before dispatching.
            mock_process.assert_called_once()
            (source_arg,) = mock_process.call_args.args
            assert isinstance(source_arg, FileSource)
            assert source_arg.path == str(small_log_file)
            assert result == ["test line"]

    def test_anomaly_mode(self, small_log_file):
        """Test anomaly processing mode"""
        reducer = LogReducer(mode="anomaly", level="enhanced")

        with patch.object(reducer, "_process_anomaly_mode") as mock_process:
            mock_process.return_value = ["anomaly line"]

            result = reducer.process_file(str(small_log_file))

            # process_file wraps the path in a FileSource before dispatching.
            mock_process.assert_called_once()
            (source_arg,) = mock_process.call_args.args
            assert isinstance(source_arg, FileSource)
            assert source_arg.path == str(small_log_file)
            assert result == ["anomaly line"]

    def test_temporal_mode(self, small_log_file):
        """Test temporal processing mode"""
        reducer = LogReducer(mode="temporal", level="enhanced")

        with patch.object(reducer, "_process_temporal_mode") as mock_process:
            mock_process.return_value = ["temporal line"]

            result = reducer.process_file(str(small_log_file))

            # process_file wraps the path in a FileSource before dispatching.
            mock_process.assert_called_once()
            (source_arg,) = mock_process.call_args.args
            assert isinstance(source_arg, FileSource)
            assert source_arg.path == str(small_log_file)
            assert result == ["temporal line"]

    def test_hybrid_mode(self, small_log_file):
        """Test hybrid processing mode"""
        reducer = LogReducer(mode="hybrid", level="enhanced")

        with patch.object(reducer, "_process_hybrid_mode") as mock_process:
            mock_process.return_value = ["hybrid line"]

            result = reducer.process_file(str(small_log_file))

            # process_file wraps the path in a FileSource before dispatching.
            mock_process.assert_called_once()
            (source_arg,) = mock_process.call_args.args
            assert isinstance(source_arg, FileSource)
            assert source_arg.path == str(small_log_file)
            assert result == ["hybrid line"]


class TestLogReducerEstimateProcessing:
    """Test processing estimation functionality"""

    def test_estimate_processing(self, small_log_file):
        """Test processing estimation"""
        reducer = LogReducer(level="standard")

        estimate = reducer.estimate_processing(str(small_log_file))

        assert isinstance(estimate, dict)
        assert "file_size_gb" in estimate
        assert "memory_required_gb" in estimate
        assert "strategy" in estimate
        assert "estimated_time_seconds" in estimate
        assert "will_sample" in estimate
        assert "estimated_output_lines" in estimate

        # Verify reasonable values
        assert estimate["file_size_gb"] >= 0
        assert estimate["memory_required_gb"] > 0
        assert estimate["strategy"] in ["full", "chunked", "sampled"]
        assert estimate["estimated_time_seconds"] >= 0
        assert isinstance(estimate["will_sample"], bool)
        assert estimate["estimated_output_lines"] >= 0


class TestLogReducerInternalMethods:
    """Test internal processing methods"""

    def test_process_pattern_mode_standard(self, small_log_file):
        """Test pattern mode processing (standard level)"""
        reducer = LogReducer(level="standard", mode="pattern")

        # _process_pattern_mode iterates the source directly; a list is a valid
        # re-iterable source. Mock dedup + extract to control the pipeline.
        with (
            patch.object(reducer.deduplicator, "deduplicate_lines") as mock_dedup,
            patch.object(reducer.pattern_extractor, "extract_patterns") as mock_extract,
        ):
            # Setup mocks
            mock_dedup.return_value = ["line1", "line2"]  # Deduplicated

            mock_pattern = Mock()
            mock_pattern.examples = ["example1", "example2"]
            mock_extract.return_value = [mock_pattern]

            result = reducer._process_pattern_mode(["line1", "line2", "line3"])

            # Verify method calls
            mock_dedup.assert_called_once()
            mock_extract.assert_called_once()

            # Verify result
            assert result == ["example1", "example2"]

    def test_process_pattern_mode_enhanced_with_fuzzy(self, small_log_file):
        """Test pattern mode processing (enhanced level with fuzzy dedup)"""
        reducer = LogReducer(level="enhanced", mode="pattern")

        with (
            patch.object(reducer.deduplicator, "deduplicate_lines") as mock_dedup,
            patch.object(reducer.fuzzy_dedup, "deduplicate") as mock_fuzzy,
            patch.object(reducer.pattern_extractor, "extract_patterns") as mock_extract,
        ):
            # Setup mocks
            mock_dedup.return_value = ["line1", "line2", "line3"]
            mock_fuzzy.return_value = ["line1", "line2"]  # Fuzzy deduplicated

            mock_pattern = Mock()
            mock_pattern.examples = ["example1"]
            mock_extract.return_value = [mock_pattern]

            result = reducer._process_pattern_mode(["line1", "line2", "line3"])

            # Verify fuzzy dedup was called
            mock_fuzzy.assert_called_once_with(["line1", "line2", "line3"])

            assert result == ["example1"]

    def test_process_anomaly_mode_fallback(self, small_log_file):
        """Test anomaly mode fallback when anomaly detector unavailable"""
        reducer = LogReducer(mode="anomaly", level="standard")
        reducer.anomaly_detector = None  # Simulate unavailable detector

        with patch.object(reducer, "_process_pattern_mode") as mock_pattern:
            mock_pattern.return_value = ["pattern fallback"]

            result = reducer._process_anomaly_mode(str(small_log_file))

            mock_pattern.assert_called_once_with(str(small_log_file))
            assert result == ["pattern fallback"]


class TestLogReducerStatefulness:
    """The reducer's analysis components must not leak state across passes/runs."""

    def test_reducer_is_reusable(self):
        """Reducing twice with one reducer must not silently return an empty set.

        Regression: the deduplicator/miner used to accumulate state, so the
        second run saw every line as already-seen and returned nothing.
        """
        reducer = LogReducer(level="standard", mode="pattern")
        lines = [f"ERROR request {i % 4} failed timeout" for i in range(80)]

        first = reducer.reduce(lines)
        second = reducer.reduce(lines)

        assert first  # non-empty
        assert second == first  # reuse yields the same result, not an empty one

    def test_hybrid_anomaly_pass_sees_deduped_input(self):
        """Hybrid's anomaly pass must get a fresh dedup, not an exhausted one.

        Regression: the pattern pass populated the shared deduplicator's
        seen-set, so the anomaly pass received an empty list and no anomaly
        could ever survive (hybrid silently degraded to pattern-only).
        """
        reducer = LogReducer(level="enhanced", mode="hybrid")
        lines = [f"INFO request {i} handled in 12ms" for i in range(60)] + ["FATAL kernel panic"]

        seen_counts = []
        real_detect = reducer.anomaly_detector.detect_anomalies

        def spy(unique_lines):
            seen_counts.append(len(unique_lines))
            return real_detect(unique_lines)

        reducer.anomaly_detector.detect_anomalies = spy
        reducer.reduce(lines)

        assert seen_counts  # the anomaly pass ran
        assert seen_counts[0] > 0  # ... and saw the deduped input, not an empty list
