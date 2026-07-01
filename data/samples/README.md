# Sample Log Files

Real-world log samples used to demonstrate and test LogReducer across different
log formats, patterns, and use cases.

## Provenance and licensing

These are public research datasets from **LogHub**, not synthetic data. Each
file is a truncated excerpt of a LogHub dataset, redistributed unmodified for
demonstration and testing. If you use them, cite LogHub:

> Jieming Zhu, Shilin He, Pinjia He, Jinyang Liu, Michael R. Lyu. "Loghub: A
> Large Collection of System Log Datasets for AI-driven Log Analytics." ISSRE
> 2023. https://github.com/logpai/loghub

Some datasets originate from public sources - the BGL and Thunderbird traces
come from the USENIX CFDR computer failure data repository (Sandia National
Laboratories). Attribution is also recorded in the top-level [NOTICE](../../NOTICE).

## Files

| File | LogHub dataset | Type |
|------|----------------|------|
| `apache_access.log` | Apache | Web server access/error logs |
| `bgl_supercomputer.log` | BGL | Blue Gene/L supercomputer logs (Sandia, via CFDR) |
| `hdfs_system.log` | HDFS | Hadoop Distributed File System logs |
| `healthapp_android.log` | HealthApp | Android health application logs |
| `linux_system.log` | Linux | Linux system (syslog) messages |
| `openstack_nova.log` | OpenStack | OpenStack Nova compute logs |
| `proxifier_network.log` | Proxifier | Proxifier network client logs |
| `spark_application.log` | Spark | Apache Spark application logs |
| `thunderbird_hpc.log` | Thunderbird | Thunderbird HPC cluster logs (Sandia, via CFDR) |
| `zookeeper_cluster.log` | Zookeeper | Apache ZooKeeper service logs |

The variety is deliberate: multiple timestamp formats (ISO 8601, Apache,
syslog, custom), structured and unstructured lines, multi-line stack traces,
and both low- and high-cardinality content - enough to exercise pattern mining,
anomaly detection, temporal grouping, and the memory-safe streaming paths.

## Usage

```bash
# Pattern extraction (default mode)
logreducer data/samples/apache_access.log

# Anomaly detection
logreducer data/samples/bgl_supercomputer.log --mode anomaly

# Temporal grouping
logreducer data/samples/openstack_nova.log --mode temporal
```

```python
import time
from logreducer import LogReducer

for path in ("apache_access", "hdfs_system", "spark_application"):
    start = time.time()
    result = LogReducer(level="enhanced").process_file(
        f"data/samples/{path}.log", return_metadata=True
    )
    pct = result["stats"]["reduction_percent"]
    print(f"{path}: {pct:.1f}% reduction in {time.time() - start:.2f}s")
```
