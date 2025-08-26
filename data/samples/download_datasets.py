#!/usr/bin/env python3
"""
Download script for public log datasets from various sources
"""

import os
import requests
import gzip
import zipfile
from pathlib import Path
from urllib.parse import urlparse
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Dataset sources with real public log files
DATASETS = {
    # LogHub - Academic research datasets (ISSRE'23)
    "apache_access.log": {
        "url": "https://raw.githubusercontent.com/logpai/loghub/master/Apache/Apache_2k.log",
        "description": "Apache HTTP server access logs (2k lines)",
        "size": "~200KB",
        "source": "LogHub Academic Dataset"
    },
    
    "hdfs_system.log": {
        "url": "https://raw.githubusercontent.com/logpai/loghub/master/HDFS/HDFS_2k.log", 
        "description": "Hadoop Distributed File System logs",
        "size": "~300KB",
        "source": "LogHub Academic Dataset"
    },
    
    "linux_system.log": {
        "url": "https://raw.githubusercontent.com/logpai/loghub/master/Linux/Linux_2k.log",
        "description": "Linux system logs with kernel messages",
        "size": "~150KB", 
        "source": "LogHub Academic Dataset"
    },
    
    "openstack_nova.log": {
        "url": "https://raw.githubusercontent.com/logpai/loghub/master/OpenStack/OpenStack_2k.log",
        "description": "OpenStack cloud infrastructure logs",
        "size": "~400KB",
        "source": "LogHub Academic Dataset"
    },
    
    "spark_application.log": {
        "url": "https://raw.githubusercontent.com/logpai/loghub/master/Spark/Spark_2k.log",
        "description": "Apache Spark distributed computing logs", 
        "size": "~250KB",
        "source": "LogHub Academic Dataset"
    },
    
    "zookeeper_cluster.log": {
        "url": "https://raw.githubusercontent.com/logpai/loghub/master/Zookeeper/Zookeeper_2k.log",
        "description": "Apache Zookeeper coordination service logs",
        "size": "~180KB",
        "source": "LogHub Academic Dataset"
    },
    
    "bgl_supercomputer.log": {
        "url": "https://raw.githubusercontent.com/logpai/loghub/master/BGL/BGL_2k.log",
        "description": "Blue Gene/L supercomputer system logs",
        "size": "~120KB",
        "source": "LogHub Academic Dataset" 
    },
    
    "thunderbird_hpc.log": {
        "url": "https://raw.githubusercontent.com/logpai/loghub/master/Thunderbird/Thunderbird_2k.log",
        "description": "Thunderbird supercomputer system logs",
        "size": "~350KB",
        "source": "LogHub Academic Dataset"
    },
    
    # Additional LogHub datasets for more variety
    "proxifier_network.log": {
        "url": "https://raw.githubusercontent.com/logpai/loghub/master/Proxifier/Proxifier_2k.log",
        "description": "Proxifier network proxy logs",
        "size": "~150KB",
        "source": "LogHub Academic Dataset"
    },
    
    "healthapp_android.log": {
        "url": "https://raw.githubusercontent.com/logpai/loghub/master/HealthApp/HealthApp_2k.log",
        "description": "Android health application logs", 
        "size": "~100KB",
        "source": "LogHub Academic Dataset"
    }
}

def download_file(url: str, filename: str, compressed: bool = False) -> bool:
    """Download a file from URL"""
    temp_file = filename + ".tmp"
    
    try:
        logger.info(f"Downloading {filename} from {url}")
        
        # Skip FTP URLs since requests doesn't support them
        if url.startswith('ftp://'):
            logger.warning(f"WARNING: Skipping FTP URL: {url}")
            logger.info(f"NOTE: FTP downloads require additional tools like ftplib or wget")
            return False
        
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        # Write to temporary file first
        with open(temp_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # Handle compressed files
        if compressed and filename.endswith('.log'):
            if url.endswith('.gz'):
                logger.info(f"Decompressing gzip file {temp_file}")
                with gzip.open(temp_file, 'rb') as gz_file:
                    with open(filename, 'wb') as out_file:
                        out_file.write(gz_file.read())
                os.remove(temp_file)
            else:
                os.rename(temp_file, filename)
        else:
            os.rename(temp_file, filename)
            
        # Get file size
        file_size = os.path.getsize(filename) / 1024 / 1024  # MB
        logger.info(f"✅ Downloaded {filename} ({file_size:.1f} MB)")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to download {filename}: {e}")
        # Clean up temp file if it exists
        if os.path.exists(temp_file):
            os.remove(temp_file)
        return False


def create_dataset_info():
    """Create README with dataset information"""
    readme_content = """# Real-World Log Datasets

This directory contains real-world log datasets downloaded from public sources for testing LogReducer.

## Available Datasets

| File | Size | Type | Source | Description |
|------|------|------|--------|-------------|
"""
    
    for filename, info in DATASETS.items():
        if os.path.exists(filename):
            actual_size = os.path.getsize(filename) / 1024 / 1024
            size_str = f"{actual_size:.1f}MB"
        else:
            size_str = info['size']
            
        readme_content += f"| `{filename}` | {size_str} | Real | {info['source']} | {info['description']} |\n"
    
    readme_content += """
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
"""
    
    with open("README.md", "w") as f:
        f.write(readme_content)
    
    logger.info("✅ Created dataset README.md")


def main():
    """Main download process"""
    logger.info("LogReducer Sample Dataset Downloader")
    print("=" * 50)
    
    # Create samples directory if it doesn't exist
    os.makedirs("samples", exist_ok=True)
    os.chdir("samples")
    
    # Track download statistics
    successful_downloads = 0
    failed_downloads = 0
    total_size = 0
    
    # Download each dataset
    for filename, info in DATASETS.items():
        logger.info(f"Dataset: {filename}")
        print(f"   Source: {info['source']}")
        print(f"   Description: {info['description']}")
        print(f"   Expected Size: {info['size']}")
        
        # Skip if file already exists
        if os.path.exists(filename):
            file_size = os.path.getsize(filename) / 1024 / 1024
            logger.warning(f"File already exists ({file_size:.1f} MB), skipping")
            successful_downloads += 1
            total_size += file_size
            continue
        
        # Download file
        compressed = info.get('compressed', False)
        if download_file(info['url'], filename, compressed):
            successful_downloads += 1
            total_size += os.path.getsize(filename) / 1024 / 1024
        else:
            failed_downloads += 1
    
    # Create dataset information
    create_dataset_info()
    
    # Summary
    print("\n" + "=" * 50)
    logger.info("Download Summary")
    print("=" * 50)
    print(f"✅ Successful downloads: {successful_downloads}")
    print(f"❌ Failed downloads: {failed_downloads}")
    print(f"📦 Total dataset size: {total_size:.1f} MB")
    print(f"📁 Files available in: {os.getcwd()}")
    
    if successful_downloads > 0:
        logger.info("Next Steps:")
        print("1. Test LogReducer on different datasets:")
        print("   python -c \"from logreducer import LogReducer; LogReducer().process_file('samples/apache_access.log')\"")
        print("2. Run comprehensive tests:")
        print("   python test_comprehensive.py")
        print("3. Benchmark performance:")
        print("   python scripts/local_ci.sh --coverage")


if __name__ == "__main__":
    main()