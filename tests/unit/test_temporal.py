"""
Unit tests for temporal processing module
"""

import time
from datetime import datetime

import pytest

from logreducer.temporal import LogEntry, TemporalProcessor, TimestampParser


class TestLogEntry:
    """Test cases for LogEntry dataclass"""

    def test_log_entry_creation(self):
        """Test LogEntry creation"""
        entry = LogEntry(raw_line="Test log line")

        assert entry.raw_line == "Test log line"
        assert entry.timestamp is None
        assert entry.level is None
        assert entry.line_number == 0

    def test_log_entry_with_data(self):
        """Test LogEntry creation with full data"""
        timestamp = datetime(2024, 1, 15, 14, 30, 25)
        entry = LogEntry(
            raw_line="2024-01-15 14:30:25 INFO Test message",
            timestamp=timestamp,
            level="INFO",
            line_number=42,
        )

        assert entry.raw_line == "2024-01-15 14:30:25 INFO Test message"
        assert entry.timestamp == timestamp
        assert entry.level == "INFO"
        assert entry.line_number == 42


class TestTimestampParser:
    """Test cases for TimestampParser"""

    def test_initialization(self):
        """Test timestamp parser initialization"""
        parser = TimestampParser()

        assert hasattr(parser, "PATTERNS")
        assert hasattr(parser, "COMPILED_PATTERNS")
        assert len(parser.COMPILED_PATTERNS) > 0

    def test_parse_line_basic(self):
        """Test basic line parsing"""
        parser = TimestampParser()

        line = "2024-01-15 14:30:25 INFO Test message"
        entry = parser.parse_line(line)

        assert isinstance(entry, LogEntry)
        assert entry.raw_line == line.strip()
        assert entry.timestamp is not None
        assert entry.level == "INFO"

    def test_parse_line_no_timestamp(self):
        """Test parsing line without timestamp"""
        parser = TimestampParser()

        line = "Just a plain log line without timestamp"
        entry = parser.parse_line(line, line_number=5)

        assert entry.raw_line == line
        assert entry.timestamp is None
        assert entry.line_number == 5

    def test_parse_line_with_different_levels(self):
        """Test parsing line with different log levels"""
        parser = TimestampParser()

        test_cases = [
            ("2024-01-15 14:30:25 DEBUG Debug message", "DEBUG"),
            ("2024-01-15 14:30:25 INFO Info message", "INFO"),
            ("2024-01-15 14:30:25 WARN Warning message", "WARN"),
            ("2024-01-15 14:30:25 ERROR Error message", "ERROR"),
            ("2024-01-15 14:30:25 CRITICAL Critical message", "CRITICAL"),
        ]

        for line, expected_level in test_cases:
            entry = parser.parse_line(line)
            assert entry.level == expected_level


class TestTemporalProcessor:
    """Test cases for TemporalProcessor"""

    def test_initialization(self):
        """Test temporal processor initialization"""
        processor = TemporalProcessor()

        assert processor.window_minutes == 60
        assert hasattr(processor, "parser")
        assert isinstance(processor.parser, TimestampParser)

    def test_initialization_custom_window(self):
        """Test temporal processor with custom window size"""
        processor = TemporalProcessor(window_minutes=30)

        assert processor.window_minutes == 30

    def test_process_temporal_empty_lines(self):
        """Test processing empty line list"""
        processor = TemporalProcessor()

        result = processor.process_temporal([])

        assert isinstance(result, dict)
        assert "temporal_patterns" in result
        assert "timeless_patterns" in result
        assert "time_distribution" in result
        assert result["temporal_patterns"] == []
        assert result["timeless_patterns"] == []

    def test_process_temporal_basic_lines(self):
        """Test processing basic lines"""
        processor = TemporalProcessor()

        lines = [
            "2024-01-15 14:30:25 INFO Test first message",
            "2024-01-15 14:30:26 INFO Test second message",
            "Plain line without timestamp",
        ]

        result = processor.process_temporal(lines)

        assert isinstance(result, dict)
        assert "temporal_patterns" in result
        assert "timeless_patterns" in result
        assert "time_distribution" in result

        # Should have some patterns
        assert isinstance(result["temporal_patterns"], list)
        assert isinstance(result["timeless_patterns"], list)

        # Should have processed timeless line
        assert len(result["timeless_patterns"]) > 0

    def test_process_temporal_timestamped_only(self):
        """Test processing only timestamped lines"""
        processor = TemporalProcessor()

        lines = [
            "2024-01-15 14:30:25 INFO First message",
            "2024-01-15 14:30:26 ERROR Error occurred",
            "2024-01-15 14:30:27 INFO Recovery successful",
        ]

        result = processor.process_temporal(lines)

        assert isinstance(result, dict)

        # Should have temporal patterns
        assert len(result["temporal_patterns"]) > 0

        # Should have time distribution
        assert "time_distribution" in result
        assert isinstance(result["time_distribution"], dict)

    def test_process_temporal_no_timestamps(self):
        """Test processing lines without timestamps"""
        processor = TemporalProcessor()

        lines = [
            "Plain log line 1",
            "Another plain line",
            "Third line without timestamp",
        ]

        result = processor.process_temporal(lines)

        assert isinstance(result, dict)

        # Should have timeless patterns
        assert len(result["timeless_patterns"]) > 0

        # Should not have temporal patterns
        assert len(result["temporal_patterns"]) == 0

    def test_timeless_entries_carry_the_final_template(self):
        """Every entry of one cluster reports the template its window ends on."""
        processor = TemporalProcessor()
        result = processor.process_temporal(["user alice logged in", "user bob logged in"])
        templates = [p["template"] for p in result["timeless_patterns"]]
        assert templates == ["user <*> logged in", "user <*> logged in"]

    def test_timed_entries_carry_the_final_template(self):
        """The first entry of a window is not left with its pre-widening template."""
        processor = TemporalProcessor()
        lines = [
            "2024-01-15 14:30:25 INFO user alice logged in",
            "2024-01-15 14:30:26 INFO user bob logged in",
        ]
        result = processor.process_temporal(lines)
        templates = {p["template"] for p in result["temporal_patterns"]}
        assert len(templates) == 1
        assert "<*>" in templates.pop()


class TestBoundaryInputs:
    """Timestamps and windows at the edge of what the processor accepts."""

    @pytest.mark.parametrize("stamp", ["0001-01-01 00:00:00", "9999-12-31 23:59:59"])
    def test_sentinel_timestamps_do_not_crash(self, stamp):
        result = TemporalProcessor().process_temporal([f"{stamp} ERROR sentinel row {i}" for i in range(3)])

        assert len(result["temporal_patterns"]) == 3
        assert len({p["window"] for p in result["temporal_patterns"]}) == 1

    def test_window_is_independent_of_local_timezone(self, monkeypatch):
        # 01:30 does not exist in London on 2024-03-31 (clocks jump to 02:00).
        lines = ["2024-03-31 01:30:00 INFO a", "2024-03-31 03:30:00 INFO b"]
        monkeypatch.setenv("TZ", "Europe/London")
        time.tzset()
        try:
            windows = [p["window"] for p in TemporalProcessor(60).process_temporal(lines)["temporal_patterns"]]
        finally:
            monkeypatch.undo()
            time.tzset()

        assert windows[1] - windows[0] == 2

    @pytest.mark.parametrize("minutes", [0, -5])
    def test_non_positive_window_rejected(self, minutes):
        with pytest.raises(ValueError, match="window_minutes"):
            TemporalProcessor(window_minutes=minutes)
