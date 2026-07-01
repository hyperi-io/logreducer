# LogReducer Examples

This directory contains real-world examples and tutorials for using LogReducer effectively.

## Quick Examples

### Basic Usage

```python
from logreducer import LogReducer

# Create a reducer with default settings
reducer = LogReducer()

# Process a log file
reduced_lines = reducer.process_file("app.log")
print(f"Reduced {len(reduced_lines)} lines")

# Save to file
reducer.process_file("app.log", "reduced.log")
```

### Advanced Configuration

```python
from logreducer import LogReducer

# High-performance processing
reducer = LogReducer(
    level="enhanced",       # Better accuracy
    mode="hybrid",          # Use all algorithms  
    max_memory_gb=4.0,      # Allow more memory
    enable_logging=True     # Enable processing logs
)

# Process with metadata
result = reducer.process_file("large.log", "output.log", return_metadata=True)
print(f"Reduction: {result['stats']['reduction_percent']:.1f}%")
```

## Command Line Examples

### Basic Processing
```bash
# Simple reduction
logreducer app.log -o reduced.log

# With statistics
logreducer app.log -o reduced.log --stats
```

### Advanced Processing
```bash
# Enhanced processing with JSON output
logreducer app.log -l enhanced -m hybrid --format json -o result.json

# Estimate processing requirements
logreducer large.log --estimate

# Maximum quality with logging
logreducer app.log -l maximum --log --log-file processing.log
```

## Use Case Examples

### 1. Development Log Analysis
Process development logs to find errors and important events:

```python
reducer = LogReducer(
    level="enhanced",
    mode="anomaly",         # Focus on unusual events
    enable_logging=True
)

# Process and find anomalies
result = reducer.process_file("dev.log", "important-events.log")
```

### 2. Production Log Monitoring
Reduce production logs while preserving critical information:

```bash
# Process hourly with hybrid approach
logreducer /var/log/app/$(date +%Y%m%d_%H).log \
    -l maximum \
    -m hybrid \
    --format jsonl \
    -o /var/log/reduced/$(date +%Y%m%d_%H).jsonl
```

### 3. Historical Log Analysis
Process large historical logs efficiently:

```python
# Memory-constrained processing for large files
reducer = LogReducer(
    level="standard",
    mode="temporal",        # Time-based sampling
    max_memory_gb=1.0       # Limit memory usage
)

for log_file in historical_logs:
    reducer.process_file(log_file, f"reduced_{log_file}")
```

## Integration Examples

### 1. Docker Container
```dockerfile
FROM python:3.12-slim

RUN pip install logreducer

# Process logs during container startup
CMD ["logreducer", "/app/logs/app.log", "-o", "/app/logs/reduced.log", "--stats"]
```

### 2. Kubernetes Job
```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: log-reduction
spec:
  template:
    spec:
      containers:
      - name: logreducer
        image: python:3.12-slim
        command: ["sh", "-c"]
        args:
        - |
          pip install logreducer
          logreducer /logs/app.log -l enhanced -m hybrid -o /output/reduced.log
        resources:
          limits:
            memory: "2Gi"
            cpu: "1000m"
      restartPolicy: Never
```

### 3. CI/CD Pipeline
```yaml
# GitHub Actions example
- name: Reduce Test Logs
  run: |
    pip install logreducer
    mkdir -p test-summary
    # The CLI reduces one file per run, so loop over the logs.
    for f in test-logs/*.log; do
      logreducer "$f" -l standard -m pattern --format json -o "test-summary/$(basename "$f").json"
    done

- name: Upload Reduced Logs
  uses: actions/upload-artifact@v4
  with:
    name: reduced-logs
    path: test-summary.json
```

## Performance Tuning Examples

### Memory-Constrained Environment
```python
# Optimize for low memory usage
reducer = LogReducer(
    level="standard",       # Faster processing
    mode="pattern",         # Less memory intensive
    max_memory_gb=0.5,      # Strict limit
    chunk_size=10000        # Smaller chunks
)
```

### High-Performance Processing
```python
# Optimize for speed
reducer = LogReducer(
    level="enhanced",       # Better algorithms
    mode="hybrid",          # All techniques
    max_memory_gb=8.0,      # Allow more memory
    hash_algorithm="xxhash" # Faster hashing (needs the 'enhanced' extra)
)
```

### Container-Optimized
```python
# Auto-detects container CPU limits
reducer = LogReducer()  # Uses all available cores

# Check detected configuration
print(f"Using {reducer.config.n_workers} worker threads")
print(f"Memory limit: {reducer.config.max_memory_gb} GB")
```

## Output Format Examples

### Line-by-Line (Default)
```bash
logreducer app.log -o reduced.log
```

### JSON Format
```bash
logreducer app.log --format json --pretty-json -o result.json
```

### JSON Lines Format
```bash
logreducer app.log --format jsonl -o result.jsonl
```

## Error Handling Examples

### Graceful Failure
```python
try:
    reducer = LogReducer(enable_logging=True)
    result = reducer.process_file("app.log", "reduced.log")
    print(f"Successfully reduced to {len(result)} lines")
except FileNotFoundError:
    print("Log file not found")
except MemoryError:
    print("Insufficient memory - try reducing max_memory_gb")
except Exception as e:
    print(f"Processing failed: {e}")
```

### Memory Limit Handling
```python
# Automatic degradation under memory pressure
reducer = LogReducer(max_memory_gb=1.0)

# Large inputs automatically switch to reservoir sampling to stay in budget
result = reducer.process_file("huge.log")
```

## Monitoring Examples

### Processing Statistics
```python
reducer = LogReducer(enable_logging=True)
result = reducer.process_file("app.log")

stats = reducer.stats
print(f"Input: {stats['input_lines']:,} lines ({stats['input_size_mb']:.1f} MB)")
print(f"Output: {stats['output_lines']:,} lines")
print(f"Reduction: {stats['reduction_percent']:.1f}%")
print(f"Processing time: {stats['processing_time_seconds']:.2f}s")
print(f"Throughput: {stats['processing_rate_mb_per_sec']:.1f} MB/sec")
```

### Memory Usage Monitoring
```python
import psutil

process = psutil.Process()
initial_memory = process.memory_info().rss / (1024**2)  # MB

reducer = LogReducer(max_memory_gb=2.0)
result = reducer.process_file("large.log")

final_memory = process.memory_info().rss / (1024**2)  # MB
print(f"Memory used: {final_memory - initial_memory:.1f} MB")
```

## Next Steps

- See the [README](../README.md) for the full API and CLI reference
- Check `tests/` for more usage examples
- Use `logreducer --help` for all CLI options