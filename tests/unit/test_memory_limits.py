"""
Memory limit tests for LogReducer

Tests that memory limits are actually enforced and the system
behaves correctly under memory constraints.
"""

import os
import tempfile

import psutil
import pytest

from logreducer import LogReducer
from logreducer.config import BigDialConfig
from logreducer.memory import MemoryMonitor
from logreducer.sources import FileSource


class TestMemoryLimits:
    """Test memory limit enforcement"""

    def test_memory_limit_configuration_respected(self):
        """Test that memory limits are properly set in configuration"""
        # Test with very small limit
        config = BigDialConfig(max_memory_gb=0.1)  # 100MB limit
        assert config.max_memory_gb == 0.1

        # Test that available memory adjustment works
        config = BigDialConfig(max_memory_gb=999.0)  # Unrealistically high
        # Clamped to 70% of the memory available when it was built, which never exceeds 70% of
        # the host's total (available memory read again here would race with other processes).
        total_gb = psutil.virtual_memory().total / (1024**3)
        assert 0 < config.max_memory_gb <= total_gb * 0.7

    def test_memory_monitor_tracks_usage(self):
        """Test that memory monitor correctly tracks memory usage"""
        monitor = MemoryMonitor(max_memory_gb=1.0)

        # Initial memory should be recorded
        initial_memory = monitor.get_current_usage_gb()
        assert initial_memory > 0

        # Should be able to check if limit is exceeded
        is_exceeded = monitor.is_limit_exceeded()
        assert isinstance(is_exceeded, bool)

        # Peak usage should be tracked
        peak_usage = monitor.get_peak_usage_gb()
        assert peak_usage >= initial_memory

    def test_memory_limit_triggers_sampling(self):
        """Test that memory limits trigger sampling mode"""
        # Create a large temporary file to force memory constraints
        large_content = []
        for i in range(10000):  # 10K lines
            large_content.append(f"[2025-08-26 10:{i:04d}:00] INFO Processing item {i} with some additional data")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("\n".join(large_content))
            temp_file = f.name

        try:
            # A limit the file overshoots tenfold selects reservoir sampling
            file_size = os.path.getsize(temp_file)
            tight_limit_gb = file_size / 1024**3 / 10
            monitor = MemoryMonitor(tight_limit_gb)
            assert monitor.estimate_file_strategy(file_size) == "sampled"

            reducer = LogReducer(level="standard", mode="pattern", max_memory_gb=tight_limit_gb)
            result = reducer.process_file(temp_file)

            # The reader keeps one reservoir of lines, and the stats count only those
            reservoir_size = min(monitor.safe_chunk_size, 100000)
            assert reducer.stats["input_lines"] == reservoir_size < len(large_content)
            assert 0 < len(result) < reducer.stats["input_lines"]

        finally:
            os.unlink(temp_file)

    def test_memory_exhaustion_graceful_degradation(self):
        """Test graceful behavior when approaching memory limits"""

        # Create content that will stress memory
        stress_content = []
        for i in range(5000):
            # Each line is roughly 100 characters
            stress_content.append(
                f"[2025-08-26 12:{i % 60:02d}:{i % 60:02d}] ERROR "
                f"Database connection failed for user_{i} with error code {i % 100} "
                f"after {i % 10} retries - full stack trace follows..."
            )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("\n".join(stress_content))
            temp_file = f.name

        try:
            # Test with progressively smaller memory limits
            memory_limits = [0.5, 0.1, 0.05]  # GB

            lines_in_memory = []
            for limit in memory_limits:
                # The monitor derives its soft limit and line budget from the configured limit.
                monitor = MemoryMonitor(limit)
                assert monitor.effective_limit == pytest.approx(limit * 0.8 * 1024**3)
                lines_in_memory.append(monitor.max_lines_in_memory)

                reducer = LogReducer(
                    level="standard",
                    mode="pattern",
                    max_memory_gb=limit,
                    enable_logging=True,
                )

                # Should complete without crashing and produce some output
                assert len(reducer.process_file(temp_file)) > 0

            # A smaller limit never allows more lines in memory
            assert lines_in_memory == sorted(lines_in_memory, reverse=True)

        finally:
            os.unlink(temp_file)

    def test_memory_limit_prevents_oom_killer(self):
        """Test that memory limits prevent out-of-memory situations"""

        # Create a file that would normally cause memory issues if fully loaded
        huge_content = []
        for i in range(20000):  # 20K lines
            huge_content.append(
                f"[2025-08-26 15:{i % 60:02d}:{i % 60:02d}] WARN "
                f"Cache miss for key 'user_session_{i}_data_chunk_{i % 1000}' "
                f"in region us-east-1 zone a caused fallback to database query "
                f"SELECT * FROM user_sessions WHERE session_id = '{i}' "
                f"AND created_at > '2025-08-26' AND status IN ('active', 'pending') "
                f"resulting in {i % 100}ms latency spike"
            )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("\n".join(huge_content))
            temp_file = f.name

        try:
            # A limit the file overshoots tenfold must select reservoir sampling
            file_size = os.path.getsize(temp_file)
            tight_limit_gb = file_size / 1024**3 / 10
            assert MemoryMonitor(tight_limit_gb).estimate_file_strategy(file_size) == "sampled"

            reducer = LogReducer(level="standard", mode="pattern", max_memory_gb=tight_limit_gb)
            result = reducer.reduce(FileSource(temp_file, max_memory_gb=tight_limit_gb))

            assert 0 < len(result) < len(huge_content)

        finally:
            os.unlink(temp_file)

    def test_memory_limit_with_different_processing_modes(self):
        """Test memory limits work with different processing modes"""

        # Create test data
        test_content = []
        for i in range(3000):
            test_content.append(
                f"[2025-08-26 16:{i % 60:02d}:{i % 60:02d}] INFO "
                f"Processing batch {i} with pattern_{i % 10} status_{i % 5}"
            )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("\n".join(test_content))
            temp_file = f.name

        try:
            memory_limit = 0.1  # 100MB
            modes = ["pattern", "anomaly", "temporal", "hybrid"]

            for mode in modes:
                reducer = LogReducer(
                    level="standard",
                    mode=mode,
                    max_memory_gb=memory_limit,
                    enable_logging=True,
                )

                result = reducer.process_file(temp_file)

                assert reducer.config.max_memory_gb == memory_limit
                assert 0 < len(result) < len(test_content), f"Mode {mode} should reduce the file"

        finally:
            os.unlink(temp_file)

    def test_memory_monitor_integration(self):
        """Test that MemoryMonitor integrates properly with LogReducer"""

        reducer = LogReducer(level="standard", max_memory_gb=1.0, enable_logging=True)

        # Should have a memory monitor
        assert hasattr(reducer, "memory_monitor") or "memory" in str(reducer.__dict__)

        # Create simple test file with varied content to avoid complete deduplication
        simple_content = [f"[2025-08-26 17:00:00] INFO Test line {i}" for i in range(100)]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("\n".join(simple_content))
            temp_file = f.name

        try:
            # Process and check stats include memory information
            result = reducer.process_file(temp_file)
            stats = reducer.stats

            assert len(result) > 0
            # Stats should include some memory-related information
            stats_str = str(stats).lower()
            assert any(keyword in stats_str for keyword in ["memory", "mb", "usage", "peak"]), (
                f"Stats missing memory info: {stats}"
            )

        finally:
            os.unlink(temp_file)


class TestMemoryMonitor:
    """Test the MemoryMonitor class specifically"""

    def test_memory_monitor_initialization(self):
        """Test MemoryMonitor initializes correctly"""
        monitor = MemoryMonitor(max_memory_gb=2.0)

        assert monitor.max_memory_bytes == 2.0 * 1024**3
        assert monitor.get_current_usage_gb() > 0
        assert monitor.get_peak_usage_gb() >= monitor.get_current_usage_gb()

    def test_memory_monitor_limit_detection(self):
        """Test memory limit detection"""
        # Set very high limit - should never be exceeded
        monitor_high = MemoryMonitor(max_memory_gb=100.0)
        assert not monitor_high.is_limit_exceeded()

        # Set very low limit - should be exceeded
        monitor_low = MemoryMonitor(max_memory_gb=0.001)  # 1MB
        assert monitor_low.is_limit_exceeded()

    def test_memory_monitor_tracks_peak(self):
        """Test that peak memory usage is tracked"""
        monitor = MemoryMonitor(max_memory_gb=10.0)

        initial_peak = monitor.get_peak_usage_gb()

        # Force some memory allocation
        big_list = [f"memory allocation test {i}" for i in range(10000)]

        # Peak should increase or stay the same
        new_peak = monitor.get_peak_usage_gb()
        assert new_peak >= initial_peak

        # Clean up
        del big_list

    def test_memory_monitor_reset(self):
        """Test memory monitor reset functionality"""
        monitor = MemoryMonitor(max_memory_gb=5.0)

        # Force some allocation
        temp_data = [f"test data {i}" * 100 for i in range(1000)]

        # Reset if method exists
        if hasattr(monitor, "reset"):
            monitor.reset()
            # Peak should be reset to current usage
            assert monitor.get_peak_usage_gb() >= monitor.get_current_usage_gb()

        del temp_data


if __name__ == "__main__":
    # Run specific memory tests
    pytest.main([__file__, "-v", "-s"])
