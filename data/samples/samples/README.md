# Real-World Log Datasets

This directory contains real-world log datasets downloaded from public sources for testing LogReducer.

## Available Datasets

| File | Size | Type | Source | Description |
|------|------|------|--------|-------------|
| `apache_access.log` | 0.2MB | Real | LogHub Academic Dataset | Apache HTTP server access logs (2k lines) |
| `hdfs_system.log` | 0.3MB | Real | LogHub Academic Dataset | Hadoop Distributed File System logs |
| `linux_system.log` | 0.2MB | Real | LogHub Academic Dataset | Linux system logs with kernel messages |
| `openstack_nova.log` | 0.6MB | Real | LogHub Academic Dataset | OpenStack cloud infrastructure logs |
| `spark_application.log` | 0.2MB | Real | LogHub Academic Dataset | Apache Spark distributed computing logs |
| `zookeeper_cluster.log` | 0.3MB | Real | LogHub Academic Dataset | Apache Zookeeper coordination service logs |
| `bgl_supercomputer.log` | 0.3MB | Real | LogHub Academic Dataset | Blue Gene/L supercomputer system logs |
| `thunderbird_hpc.log` | 0.3MB | Real | LogHub Academic Dataset | Thunderbird supercomputer system logs |
| `proxifier_network.log` | 0.2MB | Real | LogHub Academic Dataset | Proxifier network proxy logs |
| `healthapp_android.log` | 0.2MB | Real | LogHub Academic Dataset | Android health application logs |

## Dataset Sources

### LogHub (ISSRE'23)
Academic research datasets from the LogHub project, containing real system logs from various distributed systems and applications. These are widely used in log analysis research.

**Citation:** He, P., Zhu, J., Zheng, Z., & Lyu, M. R. (2017). Drain: An online log parsing approach with fixed depth tree. Proceedings of the 2017 International Conference on Web Services (ICWS), 33-40.

### NASA/LBL Archive
Historical web server access logs from NASA Kennedy Space Center, representing real-world web traffic patterns from the 1990s. Despite their age, these remain valuable benchmarks for log analysis.

## Usage Examples

```python
from logreducer import LogReducer

# Test on Apache logs
reducer = LogReducer(level="standard") 
result = reducer.process_file("samples/apache_access.log")

# Test on large NASA dataset
reducer = LogReducer(level="enhanced", max_memory_gb=1.0)
result = reducer.process_file("samples/nasa_access_jul95.log")

# Test anomaly detection on system logs  
reducer = LogReducer(mode="anomaly", level="enhanced")
result = reducer.process_file("samples/linux_system.log")
```

## Legal Notice

All datasets are publicly available and used in accordance with their respective licenses:
- LogHub datasets: Available for research and academic use
- NASA datasets: Public domain U.S. government data

No sensitive or private information is included in these datasets.
