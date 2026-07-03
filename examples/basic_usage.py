#!/usr/bin/env python3
"""
Basic LogReducer Usage Examples

This script demonstrates the most common ways to use LogReducer
for log file reduction and analysis.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import tempfile
import time

from logreducer import LogReducer, setup_logging
from logreducer.logging_config import get_logger

# Setup console logging for examples
setup_logging(enable=True, console=True, log_level="INFO")
logger = get_logger("examples")


def create_sample_log():
    """Create a sample log file for testing"""
    sample_lines = [
        "[2025-08-26 10:00:01] INFO Application started successfully",
        "[2025-08-26 10:00:02] DEBUG Loading configuration from config.yaml",
        "[2025-08-26 10:00:03] INFO Database connection established",
        "[2025-08-26 10:00:04] ERROR Failed to load user data for ID 12345",
        "[2025-08-26 10:00:05] INFO Processing batch 1 of 100",
        "[2025-08-26 10:00:06] INFO Processing batch 2 of 100",
        "[2025-08-26 10:00:07] INFO Processing batch 3 of 100",
        "[2025-08-26 10:00:08] WARN Cache miss for key 'user_sessions'",
        "[2025-08-26 10:00:09] ERROR Database connection lost",
        "[2025-08-26 10:00:10] INFO Retrying database connection",
        "[2025-08-26 10:00:11] INFO Database connection restored",
        "[2025-08-26 10:00:12] ERROR Failed to process payment for order 67890",
        "[2025-08-26 10:00:13] INFO Processing batch 4 of 100",
        "[2025-08-26 10:00:14] INFO Processing batch 5 of 100",
        "[2025-08-26 10:00:15] DEBUG Memory usage: 45% of 2GB limit",
        "[2025-08-26 10:00:16] INFO User login: alice@example.com",
        "[2025-08-26 10:00:17] INFO User login: bob@example.com",
        "[2025-08-26 10:00:18] WARN Multiple failed login attempts for charlie@example.com",
        "[2025-08-26 10:00:19] ERROR API timeout after 30s for endpoint /api/users",
        "[2025-08-26 10:00:20] INFO Application shutdown initiated",
    ]

    # Create repetitive patterns to show reduction effectiveness
    extended_lines = []
    for i in range(5):  # Repeat the pattern 5 times
        for line in sample_lines:
            # Modify timestamps to create variation
            new_line = line.replace("10:00:", f"10:{i:02d}:")
            extended_lines.append(new_line)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        f.write("\n".join(extended_lines))
        return f.name


def example_basic_usage():
    """Example 1: Basic usage with default settings"""
    logger.info("=" * 60)
    logger.info("Example 1: Basic Usage")
    logger.info("=" * 60)

    # Create sample data
    log_file = create_sample_log()
    logger.info(f"Created sample log file: {log_file}")

    try:
        # Create reducer with default settings
        reducer = LogReducer()

        # Process the file
        start_time = time.time()
        reduced_lines = reducer.process_file(log_file)
        processing_time = time.time() - start_time

        # Show results
        logger.info(f"Processing completed in {processing_time:.2f} seconds")
        logger.info(f"Reduced to {len(reduced_lines)} lines")

        # Show first few reduced lines
        logger.info("First 5 reduced lines:")
        for i, line in enumerate(reduced_lines[:5]):
            logger.info(f"  {i + 1}: {line}")

        if len(reduced_lines) > 5:
            logger.info(f"  ... and {len(reduced_lines) - 5} more lines")

    finally:
        # Clean up
        Path(log_file).unlink()


def example_with_output_file():
    """Example 2: Save output to file"""
    logger.info("\n" + "=" * 60)
    logger.info("Example 2: Save to Output File")
    logger.info("=" * 60)

    log_file = create_sample_log()
    output_file = Path(__file__).parent.parent / ".tmp" / "basic_example_output.log"
    output_file.parent.mkdir(exist_ok=True)

    try:
        reducer = LogReducer()

        # Process and save to file
        reduced_lines = reducer.process_file(log_file, str(output_file))

        print(f"[PASS] Processed and saved to: {output_file}")
        logger.info(f"Reduced to {len(reduced_lines)} lines")

        # Verify file was created
        if output_file.exists():
            file_size = output_file.stat().st_size
            print(f"? Output file size: {file_size} bytes")

            # Show file contents
            print("\nOutput file contents:")
            with open(output_file) as f:
                content = f.read()
                print(content[:500] + "..." if len(content) > 500 else content)

    finally:
        Path(log_file).unlink()
        if output_file.exists():
            output_file.unlink()


def example_with_statistics():
    """Example 3: Get processing statistics"""
    print("\n" + "=" * 60)
    print("Example 3: Processing Statistics")
    print("=" * 60)

    log_file = create_sample_log()

    try:
        reducer = LogReducer(enable_logging=True)

        # Process with metadata
        result = reducer.process_file(log_file, return_metadata=True)

        # Extract results and metadata
        if isinstance(result, dict):
            reduced_lines = result["lines"]
            metadata = result
        else:
            reduced_lines = result
            metadata = None

        # Get statistics
        stats = reducer.stats

        logger.info("Processing Statistics:")
        print(f"   Input lines:     {stats.get('input_lines', 'N/A'):,}")
        print(f"   Output lines:    {stats.get('output_lines', 'N/A'):,}")
        print(f"   Input size:      {stats.get('input_size_mb', 'N/A')} MB")
        print(f"   Reduction:       {stats.get('reduction_percent', 'N/A')}%")
        print(f"   Processing time: {stats.get('processing_time_seconds', 'N/A'):.2f}s")
        print(f"   Throughput:      {stats.get('processing_rate_mb_per_sec', 'N/A')} MB/sec")

        # Show configuration used (level/mode live on the reducer, not the config)
        config = reducer.config
        logger.info("Configuration:")
        print(f"   Processing level: {reducer.level.value}")
        print(f"   Processing mode:  {reducer.mode.value}")
        print(f"   Memory limit:     {config.max_memory_gb} GB")
        print(f"   Dedup cache:      {config.dedup_cache_size:,}")

    finally:
        Path(log_file).unlink()


def example_different_processing_modes():
    """Example 4: Different processing modes"""
    print("\n" + "=" * 60)
    print("Example 4: Different Processing Modes")
    print("=" * 60)

    log_file = create_sample_log()

    try:
        modes = ["pattern", "anomaly", "temporal", "hybrid"]
        results = {}

        for mode in modes:
            print(f"\n? Testing mode: {mode}")

            reducer = LogReducer(mode=mode)
            start_time = time.time()
            reduced_lines = reducer.process_file(log_file)
            processing_time = time.time() - start_time

            results[mode] = {
                "lines": len(reduced_lines),
                "time": processing_time,
                "reduction": reducer.stats.get("reduction_percent", 0),
            }

            print(
                f"   Lines: {len(reduced_lines)}, Time: {processing_time:.2f}s, "
                f"Reduction: {results[mode]['reduction']}%"
            )

        # Summary comparison
        logger.info("Mode Comparison:")
        print(f"   {'Mode':<10} {'Lines':<8} {'Time':<8} {'Reduction':<10}")
        print(f"   {'-' * 10} {'-' * 8} {'-' * 8} {'-' * 10}")

        for mode, result in results.items():
            print(f"   {mode:<10} {result['lines']:<8} {result['time']:<8.2f} {result['reduction']:<10.1f}%")

    finally:
        Path(log_file).unlink()


def example_memory_limited_processing():
    """Example 5: Memory-limited processing"""
    print("\n" + "=" * 60)
    print("Example 5: Memory-Limited Processing")
    print("=" * 60)

    # Create larger sample data
    large_sample = []
    for i in range(1000):  # 1000 lines
        large_sample.append(f"[2025-08-26 12:{i % 60:02d}:{i % 60:02d}] INFO Processing item {i}")
        if i % 10 == 0:  # Add some errors
            large_sample.append(f"[2025-08-26 12:{i % 60:02d}:{i % 60:02d}] ERROR Failed to process item {i}")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        f.write("\n".join(large_sample))
        large_log_file = f.name

    try:
        # Test with different memory limits
        memory_limits = [0.1, 0.5, 1.0]  # GB

        for limit in memory_limits:
            print(f"\n? Testing with {limit} GB memory limit:")

            reducer = LogReducer(max_memory_gb=limit, enable_logging=True)

            start_time = time.time()
            reduced_lines = reducer.process_file(large_log_file)
            processing_time = time.time() - start_time

            stats = reducer.stats
            print(f"   Memory limit: {limit} GB")
            print(f"   Reduced to:   {len(reduced_lines)} lines")
            print(f"   Reduction:    {stats.get('reduction_percent', 0):.1f}%")
            print(f"   Time:         {processing_time:.2f}s")

    finally:
        Path(large_log_file).unlink()


def main():
    """Run all examples"""
    print("LogReducer Basic Usage Examples")
    print("This script demonstrates common LogReducer usage patterns.\n")

    # Run all examples
    example_basic_usage()
    example_with_output_file()
    example_with_statistics()
    example_different_processing_modes()
    example_memory_limited_processing()

    print("\n" + "=" * 60)
    print("[PASS] All examples completed successfully!")
    print("=" * 60)
    print("\nNext steps:")
    print("- Try with your own log files")
    print("- Experiment with different processing levels and modes")
    print("- Use the command line interface: logreducer --help")
    print("- Check out the full documentation in README.md")


if __name__ == "__main__":
    main()
