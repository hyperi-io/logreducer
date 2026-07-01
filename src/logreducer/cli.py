#!/usr/bin/env python3
"""
LogReducer Command Line Interface

Provides a command-line interface for log reduction and analysis operations.
"""

import argparse
import json
import sys
from pathlib import Path

from . import LogReducer, __version__, setup_logging
from .logging_config import get_logger


def create_parser() -> argparse.ArgumentParser:
    """Create command line argument parser"""
    parser = argparse.ArgumentParser(
        prog="logreducer",
        description="High-performance log reduction with intelligent pattern extraction",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  logreducer app.log                              # Basic reduction to stdout
  logreducer app.log -o reduced.log              # Save to file
  logreducer app.log -l enhanced -m hybrid       # Enhanced processing
  logreducer app.log --format json -o result.json # JSON output
  logreducer app.log --estimate                   # Estimate processing requirements
  logreducer large.log --max-memory 4.0          # Limit memory usage

Processing Levels:
  standard  - Fast processing for typical logs (default)
  enhanced  - Advanced algorithms with better accuracy
  maximum   - Highest quality reduction for critical analysis

Processing Modes:
  pattern   - Pattern-based reduction using Drain algorithm (default)
  anomaly   - Anomaly detection using Isolation Forest
  temporal  - Time-series analysis for temporal patterns
  hybrid    - Combined approach using multiple techniques

Output Formats:
  line      - Line-by-line text output (default)
  json      - Structured JSON with metadata
  jsonl     - JSON Lines format
        """,
    )

    # Positional arguments
    parser.add_argument("input_file", help="Input log file to process")

    # Output options
    parser.add_argument("-o", "--output", metavar="FILE", help="Output file (default: stdout)")
    parser.add_argument(
        "--format",
        choices=["line", "json", "jsonl"],
        default="line",
        help="Output format (default: line)",
    )
    parser.add_argument("--pretty-json", action="store_true", help="Pretty print JSON output")

    # Processing options
    parser.add_argument(
        "-l",
        "--level",
        choices=["standard", "enhanced", "maximum"],
        default="standard",
        help="Processing level (default: standard)",
    )
    parser.add_argument(
        "-m",
        "--mode",
        choices=["pattern", "anomaly", "temporal", "hybrid"],
        default="pattern",
        help="Processing mode (default: pattern)",
    )

    # Resource limits
    parser.add_argument("--max-memory", type=float, metavar="GB", help="Maximum memory usage in GB")
    parser.add_argument(
        "--max-patterns",
        type=int,
        metavar="N",
        help="Maximum number of patterns to extract",
    )

    # Logging options
    parser.add_argument("--log", action="store_true", help="Enable processing logs")
    parser.add_argument("--log-file", metavar="FILE", help="Log file path")
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level",
    )

    # Analysis options
    parser.add_argument(
        "--estimate",
        action="store_true",
        help="Estimate processing requirements and exit",
    )
    parser.add_argument("--metadata", action="store_true", help="Include detailed metadata in output")
    parser.add_argument("--stats", action="store_true", help="Print processing statistics")

    # Version
    parser.add_argument("--version", action="version", version=f"LogReducer {__version__}")

    return parser


def estimate_processing(args: argparse.Namespace) -> None:
    """Estimate processing requirements for the given file"""
    try:
        reducer = LogReducer(level=args.level, mode=args.mode)
        estimate = reducer.estimate_processing(args.input_file)

        logger = get_logger("cli")
        logger.info("Processing Estimation")
        logger.info("=" * 50)
        logger.info(f"File size: {estimate['file_size_gb']:.2f} GB")
        logger.info(f"Estimated memory: {estimate['memory_required_gb']:.2f} GB")
        logger.info(f"Processing strategy: {estimate['strategy']}")
        logger.info(f"Estimated time: {estimate['estimated_time_seconds']:.0f} seconds")
        logger.info(f"Will sample data: {'Yes' if estimate['will_sample'] else 'No'}")
        logger.info(f"Expected output lines: ~{estimate['estimated_output_lines']:,}")

        if estimate["memory_required_gb"] > 8.0:
            logger.warning("Large memory requirements detected")
            logger.warning("Consider using --max-memory to limit usage")

        if estimate["will_sample"]:
            logger.info("File size requires sampling strategy")
            logger.info("Full processing may not be possible with current memory limits")

    except Exception as e:
        logger = get_logger("cli")
        logger.error(f"Error estimating processing: {e}")
        sys.exit(1)


def process_file(args: argparse.Namespace) -> None:
    """Process the log file according to arguments"""
    try:
        # Build kwargs for LogReducer
        kwargs = {
            "max_memory_gb": args.max_memory,
            "max_patterns": args.max_patterns,
            "enable_logging": args.log,
            "log_file": args.log_file,
            "log_level": args.log_level,
            "output_format": args.format,
            "pretty_json": args.pretty_json,
        }

        # Remove None values
        kwargs = {k: v for k, v in kwargs.items() if v is not None}

        # Create reducer
        reducer = LogReducer(level=args.level, mode=args.mode, **kwargs)

        # Process file
        result = reducer.process_file(args.input_file, args.output, return_metadata=args.metadata)

        # Handle output
        if not args.output:
            if args.metadata and isinstance(result, dict):
                if args.format == "json":
                    print(json.dumps(result, indent=2 if args.pretty_json else None))
                else:
                    # Print lines
                    for line in result["lines"]:
                        print(line)
            elif isinstance(result, list):
                for line in result:
                    print(line)

        # Print stats if requested
        if args.stats:
            stats = reducer.stats
            print("\nProcessing completed:", file=sys.stderr)
            print(
                f"  Input: {stats['input_lines']:,} lines ({stats['input_size_mb']:.1f} MB)",
                file=sys.stderr,
            )
            print(f"  Output: {stats['output_lines']:,} lines", file=sys.stderr)
            print(f"  Reduction: {stats['reduction_percent']:.1f}%", file=sys.stderr)
            print(f"  Time: {stats['processing_time_seconds']:.2f}s", file=sys.stderr)
            print(
                f"  Rate: {stats['processing_rate_mb_per_sec']:.1f} MB/sec",
                file=sys.stderr,
            )

    except KeyboardInterrupt:
        print("\nProcessing interrupted by user", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error processing file: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Main CLI entry point"""
    parser = create_parser()

    # Handle case with no arguments
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()

    # Setup logging with console output for CLI if enabled
    setup_logging(
        enable=args.log,
        console=args.log,  # Enable console logging if logging is enabled
        log_file=args.log_file,
        log_level=args.log_level,
    )

    # Validate input file
    if not Path(args.input_file).exists():
        print(f"Error: Input file '{args.input_file}' not found", file=sys.stderr)
        sys.exit(1)

    # Handle different modes
    if args.estimate:
        estimate_processing(args)
    else:
        process_file(args)


if __name__ == "__main__":
    main()
