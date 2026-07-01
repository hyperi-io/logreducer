LogReducer Documentation
========================

**Reduce GB-scale logs to a representative sample - a streaming Python library and CLI**

LogReducer reduces large volumes of log lines to a small, representative sample
while preserving the patterns and anomalies that matter. It ships as both a
command-line tool (``logreducer app.log``) and an IO-agnostic library, combining
pattern extraction, anomaly detection, and temporal analysis to achieve 80-95%
log reduction rates.

Key Features
------------

**High Performance**
   - Memory-safe streaming for unbounded file sizes
   - Achieves 80-95% reduction while preserving critical events
   - Processes roughly 10 MB/s on commodity hardware (see benchmarks below)

**Intelligent Processing**
   - Drain3 algorithm for pattern extraction
   - Isolation Forest for anomaly detection
   - Temporal analysis for time-series patterns
   - Hybrid mode combining all techniques

**Configurable**
   - Processing levels (Standard, Enhanced, Maximum)
   - Multiple output formats (LINE, JSON, JSONL)
   - Optional structured logging (human or JSON) with RFC 3339 timestamps

**IO-agnostic**
   - Reduce a file, a ``list[str]``, a SQL/ClickHouse query, or a Kafka topic
   - Auto-detects CPU cores (respects container limits)
   - Memory-usage controls and monitoring

Quick Start
-----------

Installation::

    pip install logreducer

Basic usage::

    from logreducer import LogReducer
    
    # Create reducer with default settings
    reducer = LogReducer()
    
    # Process a log file
    reduced_lines = reducer.process_file("app.log")
    
    # Save to file with metadata
    reducer.process_file("app.log", "reduced.log", return_metadata=True)

Command Line Interface::

    # Basic reduction
    logreducer app.log -o reduced.log
    
    # Enhanced processing with JSON output
    logreducer app.log -l enhanced -m hybrid --format json -o result.json
    
    # Estimate processing requirements
    logreducer large.log --estimate

Performance Benchmarks
----------------------

LogReducer has been tested against real-world datasets from LogHub:

.. list-table::
   :header-rows: 1

   * - Dataset
     - Original Size
     - Reduced Size
     - Reduction Rate
     - Processing Time
   * - Apache Access
     - 2.0 MB
     - 0.2 MB
     - 90.0%
     - 0.8s
   * - Linux System
     - 25.6 MB
     - 2.1 MB
     - 91.8%
     - 4.2s
   * - HDFS Namenode
     - 154.2 MB
     - 12.8 MB
     - 91.7%
     - 18.5s
   * - Spark Driver
     - 367.8 MB
     - 31.2 MB
     - 91.5%
     - 35.1s

Architecture Overview
---------------------

LogReducer uses a multi-stage processing pipeline:

1. **Input Parsing**: Stream-based file reading with encoding detection
2. **Pattern Extraction**: Drain3 algorithm for log template generation
3. **Similarity Detection**: MinHash LSH for fuzzy deduplication
4. **Anomaly Detection**: Isolation Forest for outlier identification
5. **Temporal Analysis**: Time-based pattern clustering
6. **Output Generation**: Configurable format serialization

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`