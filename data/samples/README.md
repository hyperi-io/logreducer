# Sample Log Files

This directory contains diverse sample log files to test and demonstrate LogReducer capabilities across different log formats, patterns, and use cases.

## File Overview

| File | Size | Type | Description |
|------|------|------|-------------|
| `apache_access.log` | ~5MB | Web Server | Apache HTTP access logs with various request patterns |
| `nginx_error.log` | ~3MB | Web Server | Nginx error logs with stack traces and debugging info |
| `application_mixed.log` | ~10MB | Application | Mixed application logs with INFO/WARN/ERROR patterns |
| `security_events.log` | ~2MB | Security | Security-related events with potential anomalies |
| `database_queries.log` | ~8MB | Database | Database query logs with performance metrics |
| `kubernetes_pods.log` | ~6MB | Infrastructure | Container orchestration logs |
| `financial_transactions.log` | ~4MB | Business | Financial system logs with structured data |
| `iot_sensor_data.log` | ~7MB | IoT/Telemetry | Time-series sensor readings and alerts |
| `microservices_distributed.log` | ~12MB | Distributed | Multi-service logs with trace IDs |
| `system_performance.log` | ~5MB | System | System metrics and performance monitoring |

## Testing Scenarios

Each file is designed to test specific LogReducer capabilities:

### Pattern Extraction
- **apache_access.log**: Tests handling of structured access log patterns
- **database_queries.log**: Tests pattern extraction from parameterized queries
- **microservices_distributed.log**: Tests complex pattern recognition across services

### Anomaly Detection  
- **security_events.log**: Contains planted security anomalies and intrusion attempts
- **financial_transactions.log**: Includes suspicious transaction patterns
- **system_performance.log**: Contains performance spikes and system anomalies

### Temporal Processing
- **iot_sensor_data.log**: Time-series data with temporal patterns
- **kubernetes_pods.log**: Container lifecycle events across time
- **application_mixed.log**: Application events with burst patterns

### Memory Management
- **microservices_distributed.log**: Large file testing memory limits
- **database_queries.log**: High-cardinality data testing deduplication

### Format Diversity
- Multiple timestamp formats (ISO 8601, Apache, syslog, custom)
- Different log levels and severity indicators  
- Structured (JSON) and unstructured text formats
- Multi-line stack traces and error messages

## Usage Examples

```bash
# Test basic pattern extraction
python -c "from logreducer import LogReducer; LogReducer().process_file('samples/apache_access.log')"

# Test anomaly detection on security logs
python -c "from logreducer import LogReducer; LogReducer(mode='anomaly').process_file('samples/security_events.log')"

# Test temporal processing on IoT data
python -c "from logreducer import LogReducer; LogReducer(mode='temporal').process_file('samples/iot_sensor_data.log')"

# Test memory management with large distributed logs
python -c "from logreducer import LogReducer; LogReducer(max_memory_gb=0.5).process_file('samples/microservices_distributed.log')"
```

## Benchmark Testing

These files enable comprehensive benchmarking:

```python
import time
from logreducer import LogReducer

files = [
    'samples/apache_access.log',
    'samples/microservices_distributed.log', 
    'samples/database_queries.log'
]

for file in files:
    start = time.time()
    reducer = LogReducer(level='enhanced')
    result = reducer.process_file(file, return_metadata=True)
    
    print(f"{file}: {result['stats']['reduction_percent']:.1f}% reduction in {time.time()-start:.2f}s")
```

## Data Sources Inspiration

The sample files are inspired by realistic log patterns from:
- Popular web servers (Apache, Nginx)
- Cloud-native applications (Kubernetes, microservices)
- Enterprise databases (PostgreSQL, MySQL query patterns)
- Security systems (SIEM, intrusion detection)
- Financial systems (transaction processing)
- IoT platforms (sensor networks, telemetry)
- Performance monitoring (APM, system metrics)

All sample data is synthetic and contains no real sensitive information.