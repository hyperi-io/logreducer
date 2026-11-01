"""
Unit tests for core LogReducer functionality
"""

import tracemalloc
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from logreducer.config import ProcessingLevel, ProcessingMode
from logreducer.core import LogReducer
from logreducer.memory import MemoryMonitor
from logreducer.sources import FileSource


class TestLogReducerInitialization:
    """Test LogReducer initialization"""

    def test_default_initialization(self):
        """Test LogReducer with default parameters"""
        reducer = LogReducer()

        assert reducer.level == ProcessingLevel.STANDARD
        assert reducer.mode == ProcessingMode.PATTERN
        assert reducer.config.max_memory_gb == 0.5  # Standard preset
        assert reducer.config.max_patterns == 500  # Standard preset

    def test_initialization_with_strings(self):
        """Test LogReducer initialization with string parameters"""
        reducer = LogReducer(level="enhanced", mode="anomaly")

        assert reducer.level == ProcessingLevel.ENHANCED
        assert reducer.mode == ProcessingMode.ANOMALY
        assert reducer.config.max_memory_gb == 1.0  # Enhanced preset

    def test_initialization_with_enums(self):
        """Test LogReducer initialization with enum parameters"""
        reducer = LogReducer(level=ProcessingLevel.MAXIMUM, mode=ProcessingMode.HYBRID)

        assert reducer.level == ProcessingLevel.MAXIMUM
        assert reducer.mode == ProcessingMode.HYBRID
        assert reducer.config.max_memory_gb == 2.0  # Maximum preset

    def test_initialization_with_overrides(self):
        """Test LogReducer initialization with parameter overrides"""
        reducer = LogReducer(level="standard", max_memory_gb=3.0, max_patterns=1500)

        assert reducer.config.max_memory_gb == 3.0  # Override applied
        assert reducer.config.max_patterns == 1500  # Override applied
        # Other standard values should remain
        assert reducer.config.examples_per_pattern == 2

    def test_initialization_with_kwargs(self):
        """Test LogReducer initialization with additional kwargs"""
        reducer = LogReducer(level="enhanced", dedup_cache_size=75000, drain_similarity=0.3)

        assert reducer.config.dedup_cache_size == 75000
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
            assert result[-1] == "test line"  # after the file's severe shapes

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
            assert result[-1] == "anomaly line"

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
            assert result[-1] == "temporal line"

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
            assert result[-1] == "hybrid line"


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
            patch.object(reducer.deduplicator, "deduplicate_counted") as mock_dedup,
            patch.object(reducer.pattern_extractor, "extract_counted_patterns") as mock_extract,
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
            patch.object(reducer.deduplicator, "deduplicate_counted") as mock_dedup,
            patch.object(reducer.fuzzy_dedup, "deduplicate_pairs") as mock_fuzzy,
            patch.object(reducer.pattern_extractor, "extract_counted_patterns") as mock_extract,
        ):
            # Setup mocks. Pattern mode now streams: fuzzy dedup is a generator
            # filter (deduplicate_pairs), fed the dedup output directly.
            mock_dedup.return_value = ["line1", "line2", "line3"]
            mock_fuzzy.return_value = iter(["line1", "line2"])  # Fuzzy deduplicated stream

            mock_pattern = Mock()
            mock_pattern.examples = ["example1"]
            mock_extract.return_value = [mock_pattern]

            result = reducer._process_pattern_mode(["line1", "line2", "line3"])

            # Verify the streaming fuzzy dedup was called with the dedup output
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

    def test_cap_for_anomaly_reservoir_caps(self):
        """anomaly_max_rows reservoir-caps the unique lines before detection."""
        reducer = LogReducer(mode="anomaly", level="standard", anomaly_max_rows=10)
        capped = reducer._cap_for_anomaly([f"line {i}" for i in range(100)])
        assert len(capped) == 10

    def test_cap_for_anomaly_no_cap_returns_input(self):
        """With no cap configured, the unique lines pass through untouched."""
        reducer = LogReducer(mode="anomaly", level="standard")
        lines = [f"line {i}" for i in range(50)]
        assert reducer._cap_for_anomaly(lines) is lines


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

    def test_hybrid_anomaly_pass_sees_deduped_input(self, monkeypatch):
        """Hybrid's anomaly pass must get a fresh dedup, not an exhausted one.

        Regression: the pattern pass populated the shared deduplicator's
        seen-set, so the anomaly pass received an empty list and no anomaly
        could ever survive (hybrid silently degraded to pattern-only).
        """
        reducer = LogReducer(level="enhanced", mode="hybrid")
        lines = [f"INFO request {i} handled in 12ms" for i in range(60)] + ["FATAL kernel panic"]

        detector = reducer.anomaly_detector
        assert detector is not None  # hybrid mode always builds one
        seen_counts = []
        real_detect = detector.detect_anomalies

        def spy(unique_lines):
            seen_counts.append(len(unique_lines))
            return real_detect(unique_lines)

        monkeypatch.setattr(detector, "detect_anomalies", spy)
        reducer.reduce(lines)

        assert seen_counts  # the anomaly pass ran
        assert seen_counts[0] > 0  # ... and saw the deduped input, not an empty list


def _stamp(line: str, stamped: bool) -> str:
    """Prefix an ISO timestamp whose second varies with the line, as a real log's does."""
    if not stamped:
        return line
    return f"2026-11-01T10:00:{zlib.crc32(line.encode()) % 60:02d}Z {line}"


MODES = ("pattern", "anomaly", "temporal", "hybrid")


@dataclass(frozen=True)
class SevereRow:
    """One scenario: routine lines plus ``extra``, reduced in every mode.

    Attributes:
        extra: Lines added to the routine ones.
        must_keep: Groups of which at least one member must be kept, in ``keep_in`` modes.
        max_severe: The most severe lines allowed in the output (None = unbounded).
        pinned: Whether the first extra line is kept, per mode, for behaviour that stays
            as it is (a mode left out is not pinned).
        overrides: Config overrides for the reducer.
        keep_in: Modes that must keep the ``must_keep`` groups.
        level: Processing level (enhanced switches fuzzy dedup on).
        keep_stamped: Whether the ``must_keep`` groups are also checked when the lines carry a timestamp.
    """

    extra: list[str]
    must_keep: list[list[str]]
    max_severe: int | None = None
    pinned: dict[str, bool] = field(default_factory=dict)
    overrides: dict[str, int] = field(default_factory=dict)
    keep_in: tuple[str, ...] = MODES
    level: str = "standard"
    keep_stamped: bool = True


def _letters(n: int) -> str:
    """Return a distinct lowercase word for each n, so lines differ by more than a number."""
    return "".join(chr(97 + n // 26**place % 26) for place in range(3))


SEVERE_SHAPES = [f"ERROR {_letters(n)} failed" for n in range(300)]
# They share terms the routine lines lack, so the detector scores them as anomalies.
QUIET_ANOMALIES = [f"NOTICE rotated keys for tenant t{n} using vault backend" for n in range(30)]
# More one-off templates than max_patterns (500), each ranked above a single widened severe pair.
WARN_TEMPLATES = [
    f"WARN {_letters(n)} {_letters(n + 600)} {_letters(n + 1200)} {_letters(n + 1800)}" for n in range(520)
]
# More templates than max_patterns, each seen 3 times, so each outranks a singleton ERROR.
FREQUENT_WARNS = [
    f"WARN {_letters(n)} {_letters(n + 600)} {_letters(n + 1200)} seq={k}" for n in range(520) for k in range(3)
]
LONG_COMMON = " ".join(_letters(n) for n in range(20))

SEVERE_ROWS = [
    pytest.param(SevereRow(["ERROR GET /health 200 req=9999"], [["ERROR GET /health 200 req=9999"]]), id="lone-error"),
    pytest.param(SevereRow(["FATAL GET /health 200 req=9999"], [["FATAL GET /health 200 req=9999"]]), id="lone-fatal"),
    pytest.param(
        SevereRow(["CRITICAL GET /health 200 req=9999"], [["CRITICAL GET /health 200 req=9999"]]), id="lone-critical"
    ),
    pytest.param(
        SevereRow(
            ["ERROR GET /health 200 req=9999", "ERROR GET /health 200 req=9998"],
            [["ERROR GET /health 200 req=9999", "ERROR GET /health 200 req=9998"]],
        ),
        id="two-of-one-shape",
    ),
    pytest.param(
        SevereRow(
            ["ERROR GET /health 200 req=9999", "FATAL disk full on node 7"],
            [["ERROR GET /health 200 req=9999"], ["FATAL disk full on node 7"]],
        ),
        id="two-shapes",
    ),
    pytest.param(
        SevereRow(
            ["ERROR GET /health 200 req=9999", "FATAL GET /health 200 req=9999"],
            [["ERROR GET /health 200 req=9999", "FATAL GET /health 200 req=9999"]],
            overrides={"min_pattern_occurrences": 5},
        ),
        id="two-levels-one-shape-above-min-occurrences",
    ),
    pytest.param(
        SevereRow(
            [f"ERROR GET /health 200 req={n}" for n in range(2000, 2200)],
            [[f"ERROR GET /health 200 req={n}" for n in range(2000, 2200)]],
            max_severe=3,  # examples_per_pattern (2) plus the anomaly pass's one line per shape
        ),
        id="flood-of-one-shape",
    ),
    pytest.param(
        SevereRow(SEVERE_SHAPES, [[line] for line in SEVERE_SHAPES]),
        id="every-one-of-many-severe-shapes",
    ),
    pytest.param(
        SevereRow(
            SEVERE_SHAPES + QUIET_ANOMALIES,
            [[line] for line in QUIET_ANOMALIES],  # one group each: sampling cannot stand in for the anomaly list
            keep_in=("anomaly", "hybrid"),  # the other modes keep a quiet template, not every line
            keep_stamped=False,  # stamp terms outrank these lines' terms in the tf-idf vocabulary
        ),
        id="many-severe-shapes-beside-quiet-anomalies",
    ),
    pytest.param(
        SevereRow(
            ["ERROR GET /health 200 req=9999", "FATAL GET /health 200 req=9999", *WARN_TEMPLATES],
            [["ERROR GET /health 200 req=9999", "FATAL GET /health 200 req=9999"]],
            overrides={"min_pattern_occurrences": 1},
        ),
        id="widened-severe-pair-among-more-templates-than-max-patterns",
    ),
    pytest.param(
        SevereRow(
            ["ERROR GET /health 200 req=9999"],
            [["ERROR GET /health 200 req=9999"]],
            overrides={"anomaly_max_rows": 100},
        ),
        id="lone-error-with-anomaly-row-cap",
    ),
    pytest.param(
        SevereRow(["ERROR GET /health 200 req=9999", *FREQUENT_WARNS], [["ERROR GET /health 200 req=9999"]]),
        id="singleton-error-below-more-frequent-templates-than-max-patterns",
    ),
    pytest.param(
        SevereRow(
            [f"INFO {LONG_COMMON}", f"ERROR {LONG_COMMON}"],
            [[f"ERROR {LONG_COMMON}"]],
            level="enhanced",
        ),
        id="error-near-identical-to-an-info-line-with-fuzzy-dedup",
    ),
    pytest.param(
        SevereRow(
            ["ERROR E1 failed", "ERROR E2 failed"],
            [["ERROR E1 failed"], ["ERROR E2 failed"]],
        ),
        id="identifiers-with-digits-stay-two-shapes",
    ),
    pytest.param(
        SevereRow(
            [f"ERROR E1 {LONG_COMMON}", f"ERROR E2 {LONG_COMMON}"],
            [[f"ERROR E1 {LONG_COMMON}"], [f"ERROR E2 {LONG_COMMON}"]],
            level="enhanced",
        ),
        id="severe-lines-sharing-words-with-different-identifiers-with-fuzzy-dedup",
    ),
    pytest.param(
        SevereRow(["NOTICE cache warmed in 9999 ms"], [], pinned={"pattern": False, "temporal": True}),
        id="lone-non-severe-line",
    ),
]


class TestSevereLinesSurvive:
    """A CRITICAL, FATAL or ERROR line is never merged into a quieter cluster or sampled away."""

    @pytest.mark.parametrize("stamped", [False, True], ids=["plain", "stamped"])
    @pytest.mark.parametrize("mode", MODES)
    @pytest.mark.parametrize("row", SEVERE_ROWS)
    def test_reduce(self, row, mode, stamped):
        """Reduce 540 routine lines plus the row's extras and check what survives."""
        routine = [f"INFO GET /health 200 req={i}" for i in range(500)]
        routine += [f"WARN slow query table=events ms={300 + i}" for i in range(40)]
        lines = [_stamp(line, stamped) for line in routine + row.extra]

        out = LogReducer(mode=mode, level=row.level, **row.overrides).reduce(lines)

        if mode in row.keep_in and (row.keep_stamped or not stamped):
            for group in row.must_keep:
                assert any(_stamp(member, stamped) in out for member in group), f"{group[0]!r} was dropped"
        if row.max_severe is not None:
            severe_out = [line for line in out if any(level in line for level in ("ERROR", "FATAL", "CRITICAL"))]
            assert len(severe_out) <= row.max_severe
            assert len(out) < len(lines) // 2
        if mode in row.pinned:
            assert (_stamp(row.extra[0], stamped) in out) is row.pinned[mode]


LONE_ERROR = "ERROR disk full on node 7"


def _is_severe_line(line: str) -> bool:
    return any(level in line for level in ("ERROR", "FATAL", "CRITICAL"))


class TestSevereLineSurvivesFileSampling:
    """A file the reader samples (by size, or when memory runs short) still gives up its lone ERROR."""

    @pytest.mark.parametrize("mode", MODES)
    @pytest.mark.parametrize(
        ("line_count", "max_memory_gb", "strategy", "error_at"),
        [
            pytest.param(5_000, 1e-5, "sampled", 4_000, id="size-sampled"),
            pytest.param(120_000, 0.004, "chunked", 110_000, id="memory-pressure-sampled-remainder"),
        ],
    )
    def test_reduce_file(self, tmp_path, mode, line_count, max_memory_gb, strategy, error_at):
        lines = [f"INFO GET /health 200 req={i}" for i in range(line_count)]
        lines[error_at] = LONE_ERROR
        path = tmp_path / "app.log"
        path.write_text("\n".join(lines), encoding="utf-8")
        assert MemoryMonitor(max_memory_gb).estimate_file_strategy(path.stat().st_size) == strategy

        out = LogReducer(mode=mode, anomaly_max_rows=2000).reduce(FileSource(path, max_memory_gb=max_memory_gb))

        assert LONE_ERROR in out
        assert len(out) < len(lines) // 10


def _evicting_lines() -> list[str]:
    """One severe shape returns between bursts of new templates, so a 3-cluster store evicts it each time."""
    lines = []
    for burst in range(100):
        lines.append(f"ERROR disk full on node {burst}")
        lines.extend(f"INFO {_letters(burst * 5 + n)} {_letters(burst * 5 + n + 1)} {_letters(n)} ok" for n in range(5))
    return lines


def _windowed_lines() -> list[str]:
    """One severe shape in each of 60 hourly windows."""
    start = datetime(2026, 1, 1)
    lines = []
    for hour in range(60):
        stamp = (start + timedelta(hours=hour)).strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"{stamp} ERROR disk full on node {hour}")
        lines.append(f"{stamp} INFO heartbeat ok")
    return lines


class TestOneSevereShapeGivesOneLine:
    """Output for a severe shape does not grow with how often a cluster or window is rebuilt."""

    @pytest.mark.parametrize("mode", MODES)
    @pytest.mark.parametrize(
        ("lines", "overrides"),
        [
            pytest.param(_evicting_lines(), {"max_clusters": 3}, id="cluster-eviction"),
            pytest.param(_windowed_lines(), {}, id="temporal-windows"),
        ],
    )
    def test_reduce(self, lines, overrides, mode):
        out = LogReducer(mode=mode, **overrides).reduce(lines)

        assert len([line for line in out if _is_severe_line(line)]) == 1


class _UniqueLines:
    """A re-iterable source of ``count`` distinct lines that never exists as a list."""

    def __init__(self, count: int) -> None:
        self.count = count

    def __iter__(self):
        return (f"INFO request {i} user u{i * 7919 % 100003} took {i % 977}ms path /a/{i}" for i in range(self.count))


def _anomaly_peak_bytes(count: int) -> int:
    tracemalloc.start()
    try:
        LogReducer(mode="anomaly", anomaly_max_rows=500, dedup_cache_size=1000).reduce(_UniqueLines(count))
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


@pytest.mark.parametrize("mode", ["anomaly", "hybrid"])
@pytest.mark.parametrize("cap", [1, 2, 3, 500])
def test_a_small_cap_still_returns_quiet_lines(mode, cap):
    lines = [f"INFO {_letters(n)} request {n} took {n % 7}ms" for n in range(60)] * 2

    out = LogReducer(mode=mode, max_patterns=cap).reduce(lines)

    assert 1 <= len(out) <= cap


@pytest.mark.parametrize(("cap", "expected"), [(1, 1), (3, 3), (10, 5)])
def test_too_few_lines_to_score_fill_the_anomaly_cap(cap, expected):
    lines = [f"INFO {_letters(n)} started" for n in range(5)]

    out = LogReducer(mode="anomaly", max_patterns=cap).reduce(lines)

    assert len(out) == expected
    assert set(out) <= set(lines)


def test_anomaly_peak_memory_does_not_grow_with_the_input():
    """The detector's input is sampled while the source streams, so 10x the lines costs no more memory."""
    assert _anomaly_peak_bytes(200_000) < _anomaly_peak_bytes(20_000) * 1.5


class _SevereFlood:
    """A re-iterable source of ``count`` severe lines that share a shape but not a Drain cluster.

    Every number differs, so no two lines reach Drain's similarity threshold and each would
    start a cluster of its own.
    """

    def __init__(self, count: int) -> None:
        self.count = count

    def __iter__(self):
        return (
            f"ERROR {i} {i * 7919 % 100003} {i * 31 % 9973} {i % 977} {i * 13 % 8191} {i * 17 % 4093}"
            for i in range(self.count)
        )


class _QuietFlood:
    """A re-iterable source of ``count`` quiet lines that share no word, so each is a new template and fuzzy-unique."""

    def __init__(self, count: int) -> None:
        self.count = count

    def __iter__(self):
        return (
            f"svc{i} req{i * 7919 % 100003} user{i * 31} took{i % 977} path{i * 13} ok{i * 17}"
            for i in range(self.count)
        )


def _pattern_flood_run(source, level: str = "standard", count: int = 5_000) -> tuple[list[str], int]:
    tracemalloc.start()
    try:
        out = LogReducer(
            level=level, mode="pattern", max_clusters=5, dedup_cache_size=1000, typed_masking=False
        ).reduce(source(count))
        return out, tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def test_severe_flood_of_one_shape_gives_one_line_in_bounded_memory():
    """Severe lines are held by the source tap alone, so the pattern miner's store does not grow with them."""
    _, small_peak = _pattern_flood_run(_SevereFlood, count=5_000)
    out, large_peak = _pattern_flood_run(_SevereFlood, count=50_000)

    assert out == ["ERROR 0 0 0 0 0 0"]
    assert large_peak < small_peak * 1.5


@pytest.mark.parametrize("level", ["standard", "enhanced", "maximum"])
def test_quiet_flood_of_new_templates_runs_in_bounded_memory(level):
    """Evicted clusters and the fuzzy index are bounded, so 10x the distinct lines costs no more memory."""
    _, small_peak = _pattern_flood_run(_QuietFlood, level, count=5_000)
    _, large_peak = _pattern_flood_run(_QuietFlood, level, count=50_000)

    assert large_peak < small_peak * 1.5
