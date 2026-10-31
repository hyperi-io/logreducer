"""Temporal processing and time-aware pattern extraction."""

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .template_mining import TemplateMiner


@dataclass
class LogEntry:
    """Parsed log entry with timestamp."""

    raw_line: str
    timestamp: datetime | None = None
    level: str | None = None
    line_number: int = 0


class TimestampParser:
    """Parse timestamps from various formats."""

    PATTERNS = [
        (r"\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}", "%Y-%m-%d %H:%M:%S"),
        (r"\d{1,2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2}", "%d/%b/%Y:%H:%M:%S"),
        (r"\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}", "%b %d %H:%M:%S"),
    ]

    COMPILED_PATTERNS = [(re.compile(p), f) for p, f in PATTERNS]
    LEVEL_PATTERN = re.compile(r"\b(DEBUG|INFO|WARN|ERROR|CRITICAL)\b", re.I)

    def parse_line(self, line: str, line_number: int = 0) -> LogEntry:
        """Parse log line."""
        entry = LogEntry(raw_line=line.strip(), line_number=line_number)

        # Extract timestamp
        for pattern, date_format in self.COMPILED_PATTERNS:
            match = pattern.search(line)
            if match:
                try:
                    timestamp_str = match.group()
                    if "%Y" not in date_format:
                        timestamp_str = f"{datetime.now().year} {timestamp_str}"
                        date_format = f"%Y {date_format}"
                    entry.timestamp = datetime.strptime(timestamp_str.replace("T", " "), date_format)
                    break
                except (ValueError, TypeError):
                    # Timestamp parsing failed, try next pattern
                    pass

        # Extract level
        level_match = self.LEVEL_PATTERN.search(line)
        if level_match:
            entry.level = level_match.group().upper()

        return entry


class TemporalProcessor:
    """Time-aware log processing."""

    def __init__(self, window_minutes: int = 60):
        if window_minutes < 1:
            raise ValueError(f"window_minutes must be at least 1, got {window_minutes!r}")
        self.window_minutes = window_minutes
        self.parser = TimestampParser()
        self.miners_by_window: dict[int, TemplateMiner] = {}

    def process_temporal(self, lines: list[str]) -> dict:
        """Process with temporal awareness."""
        entries = [self.parser.parse_line(line, i) for i, line in enumerate(lines)]

        timed = [e for e in entries if e.timestamp]
        timeless = [e for e in entries if not e.timestamp]

        results: dict[str, Any] = {
            "temporal_patterns": [],
            "timeless_patterns": [],
            "time_distribution": {},
        }

        if timed:
            results["temporal_patterns"] = self._extract_temporal_patterns(timed)
            results["time_distribution"] = self._analyze_distribution(timed)

        if timeless:
            results["timeless_patterns"] = self._extract_timeless_patterns(timeless)

        return results

    def _extract_temporal_patterns(self, entries: list[LogEntry]) -> list[dict]:
        """Extract patterns with time context."""
        patterns = []
        windows = defaultdict(list)

        # Group by time window
        for entry in entries:
            if entry.timestamp:
                # Read the naive timestamp as UTC: local-time conversion raises on
                # sentinels like 0001-01-01 and 9999-12-31 and shifts with DST.
                epoch_seconds = entry.timestamp.replace(tzinfo=UTC).timestamp()
                window_key = int(epoch_seconds // (self.window_minutes * 60))
                windows[window_key].append(entry)

        # One pattern per template within each window.
        for window_key, window_entries in windows.items():
            if window_key not in self.miners_by_window:
                self.miners_by_window[window_key] = TemplateMiner()

            for pattern in self._summarise(self.miners_by_window[window_key], window_entries):
                patterns.append({**pattern, "window": window_key})

        return patterns

    def _extract_timeless_patterns(self, entries: list[LogEntry]) -> list[dict]:
        """Extract patterns without timestamps."""
        return self._summarise(TemplateMiner(), entries)

    @staticmethod
    def _summarise(miner: TemplateMiner, entries: list[LogEntry]) -> list[dict]:
        """One dict per template: its final template, how many entries share it, and the first of them."""
        by_cluster: dict[int, dict] = {}
        clusters = {}
        for entry in entries:
            cluster = miner.add_log_message(entry.raw_line)
            clusters[cluster.cluster_id] = cluster
            summary = by_cluster.setdefault(cluster.cluster_id, {"count": 0, "example": entry.raw_line})
            summary["count"] += 1

        # Templates are read once the feed ends, after later lines have widened their slots.
        return [
            {"template": clusters[cluster_id].get_template(), **summary} for cluster_id, summary in by_cluster.items()
        ]

    def _analyze_distribution(self, entries: list[LogEntry]) -> dict:
        """Analyze time distribution."""
        dist: dict[str, Any] = {"hourly": defaultdict(int), "levels": defaultdict(int)}

        for entry in entries:
            if entry.timestamp:
                dist["hourly"][entry.timestamp.hour] += 1
            if entry.level:
                dist["levels"][entry.level] += 1

        return dist
