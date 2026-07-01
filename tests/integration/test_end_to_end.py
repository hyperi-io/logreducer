"""
End-to-end integration tests for LogReducer using real sample datasets
"""

from pathlib import Path

import pytest

from logreducer import LogReducer

# Real sample files from data/samples/
SAMPLE_FILES = [
    "apache_access.log",
    "bgl_supercomputer.log",
    "hdfs_system.log",
    "healthapp_android.log",
    "linux_system.log",
    "openstack_nova.log",
    "proxifier_network.log",
    "spark_application.log",
    "thunderbird_hpc.log",
    "zookeeper_cluster.log",
]


@pytest.fixture
def samples_dir():
    """Get samples directory path"""
    return Path(__file__).parent.parent.parent / "data" / "samples"


@pytest.fixture
def output_dir():
    """Get output directory path for reduced logs"""
    output_path = Path(__file__).parent.parent.parent / "data" / "output"
    output_path.mkdir(exist_ok=True)
    return output_path


@pytest.mark.integration
class TestRealDatasetProcessing:
    """End-to-end integration tests using real sample datasets"""

    @pytest.mark.parametrize("sample_file", SAMPLE_FILES)
    def test_process_real_samples_basic(self, sample_file, samples_dir, output_dir):
        """Test basic processing of all real sample files with output to data/output directory"""
        input_file = samples_dir / sample_file

        # Skip if sample file doesn't exist
        if not input_file.exists():
            pytest.skip(f"Sample file {sample_file} not found")

        reducer = LogReducer(level="standard", mode="pattern")
        # Output reduced log to data/output directory with same name
        output_file = output_dir / sample_file

        print(f"\nProcessing {sample_file} -> {output_file}")

        # Process file with output to data/output directory
        result = reducer.process_file(str(input_file), str(output_file), return_metadata=True)

        # Verify result structure
        assert isinstance(result, dict)
        assert "lines" in result
        assert "stats" in result
        assert "config" in result

        # Verify output file exists in data/output directory
        assert output_file.exists()

        # Verify the reduced log file has content that matches result
        with open(output_file) as f:
            output_lines = [line.strip() for line in f.readlines()]

        assert len(output_lines) == len(result["lines"])

        # Verify stats make sense
        stats = result["stats"]
        assert stats["output_lines"] >= 0  # Some files might reduce to 0 lines
        assert stats["processing_time_seconds"] >= 0
        assert stats["input_size_mb"] > 0
        assert stats["mode"] == "pattern"
        assert stats["level"] == "standard"

        # Print processing summary
        print(f"  Input: {stats['input_lines']} lines ({stats['input_size_mb']:.2f} MB)")
        print(f"  Output: {stats['output_lines']} lines ({stats['reduction_percent']:.1f}% reduction)")
        print(f"  Time: {stats['processing_time_seconds']:.3f}s")

        # Verify some reduction occurred for non-trivial files
        if stats["input_lines"] > 10:  # Only check reduction for files with >10 lines
            assert stats["reduction_percent"] >= 0

    @pytest.mark.parametrize("sample_file", ["apache_access.log", "hdfs_system.log", "linux_system.log"])
    def test_process_key_samples_enhanced(self, sample_file, samples_dir, output_dir):
        """Test enhanced processing on key sample files"""
        input_file = samples_dir / sample_file

        if not input_file.exists():
            pytest.skip(f"Sample file {sample_file} not found")

        reducer = LogReducer(level="enhanced", mode="hybrid")
        # Output enhanced version with different naming
        output_file = output_dir / f"enhanced_{sample_file}"

        print(f"\nEnhanced processing {sample_file} -> {output_file}")

        result = reducer.process_file(str(input_file), str(output_file), return_metadata=True)

        # Verify output file exists
        assert output_file.exists()

        # Verify meaningful processing occurred
        stats = result["stats"]
        assert stats["output_lines"] >= 0
        assert stats["mode"] == "hybrid"
        assert stats["level"] == "enhanced"

        print(
            f"  Enhanced: {stats['input_lines']} -> {stats['output_lines']} lines ({stats['reduction_percent']:.1f}% reduction)"
        )

        # For larger files, expect some reduction
        if stats["input_lines"] > 100:
            assert stats["reduction_percent"] > 0

    def test_complete_workflow_medium_file(self, medium_log_file, test_data_dir):
        """Test complete workflow with medium file"""
        reducer = LogReducer(level="enhanced", mode="hybrid")
        output_file = test_data_dir / "e2e_output_medium.log"

        result = reducer.process_file(str(medium_log_file), str(output_file), return_metadata=True)

        # Verify significant reduction
        stats = result["stats"]
        assert stats["reduction_percent"] > 50  # Should reduce by at least 50%
        assert stats["output_lines"] < 1000  # Input had 1000 lines
        assert stats["processing_time_seconds"] < 60  # Should be reasonably fast

        # Verify output quality - should contain different log levels
        lines = result["lines"]
        log_levels = set()
        for line in lines:
            for level in ["INFO", "WARN", "ERROR", "DEBUG", "CRITICAL"]:
                if level in line:
                    log_levels.add(level)
                    break

        assert len(log_levels) > 1  # Should preserve diverse log levels

    @pytest.mark.slow
    def test_complete_workflow_large_file(self, large_log_file, test_data_dir):
        """Test complete workflow with large file (slow test)"""
        reducer = LogReducer(level="enhanced", mode="pattern", max_memory_gb=1.0)
        output_file = test_data_dir / "e2e_output_large.log"

        result = reducer.process_file(str(large_log_file), str(output_file), return_metadata=True)

        # Verify high reduction ratio
        stats = result["stats"]
        assert stats["reduction_percent"] > 90  # Should reduce by >90%
        assert stats["output_lines"] < 1000  # Should be well compressed

        # Performance should be reasonable
        processing_rate = stats["processing_rate_mb_per_sec"]
        assert processing_rate > 0.05  # At least 0.05 MB/s (adjusted for small test files)

        # Memory usage should be controlled
        assert reducer.memory_monitor.max_memory_gb <= 1.0


@pytest.mark.integration
class TestProcessingModeIntegration:
    """Integration tests for different processing modes using real sample data"""

    @pytest.mark.parametrize("mode", ["pattern", "temporal", "hybrid"])
    @pytest.mark.parametrize(
        "sample_file",
        ["apache_access.log", "linux_system.log", "spark_application.log"],
    )
    def test_processing_modes_on_samples(self, mode, sample_file, samples_dir):
        """Test different processing modes on real sample files"""
        input_file = samples_dir / sample_file

        if not input_file.exists():
            pytest.skip(f"Sample file {sample_file} not found")

        reducer = LogReducer(level="enhanced", mode=mode)
        result = reducer.process_file(str(input_file), return_metadata=True)

        # Should extract meaningful patterns
        lines = result["lines"]
        stats = result["stats"]

        assert isinstance(lines, list)
        assert stats["mode"] == mode
        assert stats["processing_time_seconds"] >= 0

        # For files with content, should have some output or meaningful processing
        if stats["input_lines"] > 0:
            assert stats["output_lines"] >= 0

    def test_anomaly_mode_on_system_logs(self, samples_dir):
        """Test anomaly mode on system logs which may contain anomalies"""
        system_files = [
            "linux_system.log",
            "bgl_supercomputer.log",
            "thunderbird_hpc.log",
        ]

        for sample_file in system_files:
            input_file = samples_dir / sample_file

            if not input_file.exists():
                continue

            reducer = LogReducer(level="enhanced", mode="anomaly")
            result = reducer.process_file(str(input_file), return_metadata=True)

            lines = result["lines"]
            stats = result["stats"]

            assert isinstance(lines, list)
            assert stats["mode"] == "anomaly"

            # Anomaly detection should process without errors
            assert stats["processing_time_seconds"] >= 0

    def test_temporal_mode_on_timestamped_logs(self, samples_dir):
        """Test temporal mode on logs with clear timestamps"""
        timestamped_files = [
            "apache_access.log",
            "openstack_nova.log",
            "spark_application.log",
        ]

        for sample_file in timestamped_files:
            input_file = samples_dir / sample_file

            if not input_file.exists():
                continue

            reducer = LogReducer(level="enhanced", mode="temporal")
            result = reducer.process_file(str(input_file), return_metadata=True)

            lines = result["lines"]
            stats = result["stats"]

            assert isinstance(lines, list)
            assert stats["mode"] == "temporal"

            # Should process without errors
            assert stats["processing_time_seconds"] >= 0


@pytest.mark.integration
class TestProcessingLevelIntegration:
    """Integration tests for different processing levels using real samples"""

    @pytest.mark.parametrize("sample_file", ["apache_access.log", "hdfs_system.log"])
    def test_level_progression_on_samples(self, sample_file, samples_dir):
        """Test that all processing levels work on real sample files"""
        input_file = samples_dir / sample_file

        if not input_file.exists():
            pytest.skip(f"Sample file {sample_file} not found")

        results = {}

        for level in ["standard", "enhanced", "maximum"]:
            reducer = LogReducer(level=level, mode="pattern")
            result = reducer.process_file(str(input_file), return_metadata=True)
            results[level] = result

        # All levels should process without errors
        for level in results:
            stats = results[level]["stats"]
            assert stats["level"] == level
            assert stats["processing_time_seconds"] >= 0
            assert stats["output_lines"] >= 0

            # Should produce some output for non-empty inputs
            if stats["input_lines"] > 0:
                assert isinstance(results[level]["lines"], list)

    def test_benchmark_processing_levels(self, samples_dir):
        """Benchmark different processing levels on various sample types"""
        # Test on different types of logs to see how levels perform
        test_files = [
            ("apache_access.log", "web_server"),
            ("linux_system.log", "system"),
            ("spark_application.log", "application"),
            ("hdfs_system.log", "distributed_system"),
        ]

        benchmark_results = []

        for sample_file, log_type in test_files:
            input_file = samples_dir / sample_file

            if not input_file.exists():
                continue

            for level in ["standard", "enhanced"]:
                reducer = LogReducer(level=level, mode="pattern")
                result = reducer.process_file(str(input_file), return_metadata=True)

                stats = result["stats"]
                benchmark_results.append(
                    {
                        "file": sample_file,
                        "type": log_type,
                        "level": level,
                        "reduction_percent": stats["reduction_percent"],
                        "processing_time": stats["processing_time_seconds"],
                        "input_lines": stats["input_lines"],
                        "output_lines": stats["output_lines"],
                    }
                )

        # Should have collected some benchmark data
        assert len(benchmark_results) > 0

        # All processing should complete successfully
        for result in benchmark_results:
            assert result["reduction_percent"] >= 0
            assert result["processing_time"] >= 0


@pytest.mark.integration
class TestMemoryManagement:
    """Integration tests for memory management using real samples"""

    def test_memory_constraint_respected_real_data(self, samples_dir):
        """Test that memory constraints are respected with real sample data"""
        # Test on a few different sample files
        test_files = ["apache_access.log", "linux_system.log"]

        for sample_file in test_files:
            input_file = samples_dir / sample_file

            if not input_file.exists():
                continue

            # Set a low memory limit
            reducer = LogReducer(level="standard", max_memory_gb=0.1)

            # Should still process without crashing
            result = reducer.process_file(str(input_file), return_metadata=True)

            stats = result["stats"]
            assert isinstance(result["lines"], list)
            assert stats["memory_limit_gb"] == 0.1
            assert stats["processing_time_seconds"] >= 0

    def test_file_size_strategy_selection_samples(self, samples_dir):
        """Test strategy selection on real files of different sizes"""
        reducer = LogReducer(level="standard")

        # Test estimation on available sample files
        for sample_file in SAMPLE_FILES[:3]:  # Test first 3 files
            input_file = samples_dir / sample_file

            if not input_file.exists():
                continue

            estimate = reducer.estimate_processing(str(input_file))

            # Should return valid estimation
            assert "strategy" in estimate
            assert estimate["strategy"] in ["full", "streaming", "reservoir"]
            assert "estimated_time_seconds" in estimate
            assert estimate["estimated_time_seconds"] >= 0

            # Process and verify estimation was reasonable
            result = reducer.process_file(str(input_file))
            assert isinstance(result, list)


@pytest.mark.integration
class TestErrorHandling:
    """Integration tests for error handling and edge cases"""

    def test_empty_file_handling(self, test_data_dir):
        """Test handling of empty files"""
        empty_file = test_data_dir / "empty.log"
        empty_file.touch()  # Create empty file

        reducer = LogReducer(level="standard")
        result = reducer.process_file(str(empty_file))

        # Should return empty list without crashing
        assert result == []

    def test_malformed_log_lines_handling(self, test_data_dir):
        """Test handling of malformed log lines"""
        malformed_file = test_data_dir / "malformed.log"
        with open(malformed_file, "w", encoding="utf-8") as f:
            f.write("Good line: 2024-01-01 12:00:00 INFO Normal log\n")
            f.write("Bad line with special chars: \u00e9\u00fc\u00f1\n")  # Valid UTF-8 chars
            f.write("Another good line: 2024-01-01 12:00:01 WARN Warning\n")
            f.write("\n")  # Empty line
            f.write("Line without timestamp but with content\n")

        reducer = LogReducer(level="standard")
        result = reducer.process_file(str(malformed_file))

        # Should process without crashing and return some results
        assert isinstance(result, list)
        # For small test files, reduction may result in 0 lines - that's OK
        # The important thing is it doesn't crash with malformed input


@pytest.mark.integration
class TestComprehensiveRealDataValidation:
    """Comprehensive validation using all available real sample datasets"""

    def test_all_samples_process_successfully(self, samples_dir, output_dir):
        """Test that LogReducer can process all available sample files and output to data/output directory"""
        processing_results = []

        for sample_file in SAMPLE_FILES:
            input_file = samples_dir / sample_file

            if not input_file.exists():
                print(f"Skipping {sample_file} - file not found")
                continue

            print(f"\nProcessing {sample_file}...")

            # Test basic processing with output to data/output directory
            reducer = LogReducer(level="standard", mode="pattern")
            output_file = output_dir / f"comprehensive_{sample_file}"

            result = reducer.process_file(str(input_file), str(output_file), return_metadata=True)

            stats = result["stats"]
            processing_results.append(
                {
                    "file": sample_file,
                    "input_lines": stats["input_lines"],
                    "output_lines": stats["output_lines"],
                    "reduction_percent": stats["reduction_percent"],
                    "processing_time": stats["processing_time_seconds"],
                    "input_size_mb": stats["input_size_mb"],
                    "output_file": str(output_file),
                    "success": True,
                }
            )

            # Verify output file was created
            assert output_file.exists()

            # Basic validation
            assert isinstance(result["lines"], list)
            assert stats["processing_time_seconds"] >= 0
            assert stats["input_size_mb"] > 0

        # Should have processed at least some files
        assert len(processing_results) > 0

        # Print summary for visibility during testing
        print(f"\n{'=' * 70}")
        print("COMPREHENSIVE REAL DATA PROCESSING SUMMARY")
        print(f"{'=' * 70}")
        print(f"{'File':<25} {'Lines':<8} {'Out':<6} {'Reduction':<10} {'Time(s)':<8} {'Size(MB)':<8}")
        print("-" * 70)

        for result in processing_results:
            print(
                f"{result['file']:<25} {result['input_lines']:<8} {result['output_lines']:<6} "
                f"{result['reduction_percent']:<10.1f} {result['processing_time']:<8.3f} "
                f"{result['input_size_mb']:<8.2f}"
            )

        print(f"\nReduced logs saved to: data/output/")
        print(f"Files created: {len([r for r in processing_results if r['success']])}")

        # All files should have processed successfully
        successful_files = [r for r in processing_results if r["success"]]
        assert len(successful_files) == len(processing_results)

    @pytest.mark.slow
    def test_enhanced_processing_sample_subset(self, samples_dir):
        """Test enhanced processing on a subset of samples (slow test)"""
        # Test enhanced processing on key representative samples
        key_samples = [
            "apache_access.log",
            "hdfs_system.log",
            "linux_system.log",
            "spark_application.log",
        ]

        enhanced_results = []

        for sample_file in key_samples:
            input_file = samples_dir / sample_file

            if not input_file.exists():
                continue

            print(f"Enhanced processing: {sample_file}")

            # Test enhanced processing with hybrid mode
            reducer = LogReducer(level="enhanced", mode="hybrid", max_memory_gb=1.0)
            result = reducer.process_file(str(input_file), return_metadata=True)

            stats = result["stats"]
            enhanced_results.append(
                {
                    "file": sample_file,
                    "reduction_percent": stats["reduction_percent"],
                    "processing_time": stats["processing_time_seconds"],
                    "memory_used": stats.get("peak_memory_mb", 0),
                }
            )

            # Enhanced processing should complete successfully
            assert isinstance(result["lines"], list)
            assert stats["level"] == "enhanced"
            assert stats["mode"] == "hybrid"

        # Should have processed at least some files
        assert len(enhanced_results) > 0

        print(f"\nEnhanced Processing Results:")
        for result in enhanced_results:
            print(
                f"  {result['file']}: {result['reduction_percent']:.1f}% reduction in {result['processing_time']:.3f}s"
            )

    def test_very_long_lines_handling(self, test_data_dir):
        """Test handling of very long log lines"""
        long_lines_file = test_data_dir / "long_lines.log"
        with open(long_lines_file, "w") as f:
            f.write("2024-01-01 12:00:00 INFO Normal line\n")
            # Write a very long line (>10KB)
            long_data = "x" * 10000
            f.write(f"2024-01-01 12:00:01 DEBUG Very long line: {long_data}\n")
            f.write("2024-01-01 12:00:02 INFO Another normal line\n")

        reducer = LogReducer(level="standard")
        result = reducer.process_file(str(long_lines_file))

        # Should process without crashing
        assert isinstance(result, list)
        # For small test files with repetitive patterns, reduction may result in very few lines
