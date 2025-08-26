#!/usr/bin/env python3
"""
Performance benchmarking script for LogReducer

Runs comprehensive benchmarks against LogHub datasets to measure:
- Processing speed (MB/sec)
- Memory usage
- Reduction rates
- Algorithm performance across different log types

Usage:
    python scripts/benchmark.py [--dataset DATASET] [--verbose] [--output FILE]
"""

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from logreducer import LogReducer
from logreducer.config import ProcessingLevel, ProcessingMode
import psutil


class BenchmarkRunner:
    """Runs comprehensive benchmarks on LogReducer"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.samples_dir = project_root / "data" / "samples" / "samples"
        self.results_dir = project_root / ".tmp" / "benchmarks"
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
    def get_available_datasets(self) -> List[Dict[str, str]]:
        """Get all available sample datasets"""
        datasets = []
        
        if not self.samples_dir.exists():
            print(f"WARNING: Samples directory not found: {self.samples_dir}")
            return datasets
            
        for log_file in self.samples_dir.glob("*.log"):
            # Get file size
            size_mb = log_file.stat().st_size / (1024 * 1024)
            
            datasets.append({
                "name": log_file.stem,
                "path": str(log_file),
                "size_mb": round(size_mb, 2)
            })
        
        return sorted(datasets, key=lambda x: x["size_mb"])
    
    def benchmark_dataset(self, dataset: Dict[str, str], 
                         processing_levels: List[ProcessingLevel] = None,
                         processing_modes: List[ProcessingMode] = None) -> Dict:
        """Benchmark a single dataset with different configurations"""
        
        if processing_levels is None:
            processing_levels = [ProcessingLevel.STANDARD, ProcessingLevel.ENHANCED]
            
        if processing_modes is None:
            processing_modes = [ProcessingMode.PATTERN, ProcessingMode.ANOMALY, 
                              ProcessingMode.TEMPORAL, ProcessingMode.HYBRID]
        
        dataset_results = {
            "dataset": dataset["name"],
            "file_size_mb": dataset["size_mb"],
            "configurations": []
        }
        
        print(f"\nBenchmarking {dataset['name']} ({dataset['size_mb']} MB)")
        
        for level in processing_levels:
            for mode in processing_modes:
                config_name = f"{level.value}_{mode.value}"
                print(f"  🔄 Testing {config_name}...")
                
                try:
                    result = self._run_single_benchmark(
                        dataset["path"], level, mode
                    )
                    result["configuration"] = config_name
                    result["level"] = level.value
                    result["mode"] = mode.value
                    dataset_results["configurations"].append(result)
                    
                    print(f"    ✅ {result['processing_time_sec']:.1f}s, "
                          f"{result['reduction_percent']:.1f}% reduction, "
                          f"{result['throughput_mb_sec']:.1f} MB/s")
                    
                except Exception as e:
                    print(f"    ❌ Failed: {e}")
                    dataset_results["configurations"].append({
                        "configuration": config_name,
                        "level": level.value,
                        "mode": mode.value,
                        "error": str(e)
                    })
        
        return dataset_results
    
    def _run_single_benchmark(self, file_path: str, 
                             level: ProcessingLevel, 
                             mode: ProcessingMode) -> Dict:
        """Run a single benchmark configuration"""
        
        # Monitor system resources
        process = psutil.Process()
        start_memory = process.memory_info().rss / (1024 * 1024)  # MB
        
        # Create reducer
        reducer = LogReducer(level=level.value, mode=mode.value, enable_logging=False)
        
        # Run processing with timing
        start_time = time.time()
        
        output_file = self.results_dir / f"benchmark_{level.value}_{mode.value}.log"
        reduced_lines = reducer.process_file(file_path, str(output_file))
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Get final memory usage
        peak_memory = process.memory_info().rss / (1024 * 1024)  # MB
        memory_used = peak_memory - start_memory
        
        # Get statistics
        stats = reducer.stats
        
        # Calculate metrics
        file_size_mb = stats.get('input_size_mb', 0)
        throughput = file_size_mb / processing_time if processing_time > 0 else 0
        
        return {
            "processing_time_sec": round(processing_time, 2),
            "throughput_mb_sec": round(throughput, 1),
            "input_lines": stats.get('input_lines', 0),
            "output_lines": stats.get('output_lines', 0),
            "reduction_percent": round(stats.get('reduction_percent', 0), 1),
            "memory_used_mb": round(memory_used, 1),
            "peak_memory_mb": round(peak_memory, 1),
            "cpu_cores_used": reducer.config.n_workers
        }
    
    def run_comprehensive_benchmark(self, dataset_filter: Optional[str] = None) -> Dict:
        """Run comprehensive benchmarks on all available datasets"""
        
        datasets = self.get_available_datasets()
        
        if not datasets:
            print("❌ No datasets found for benchmarking")
            return {"error": "No datasets available"}
        
        # Filter datasets if requested
        if dataset_filter:
            datasets = [d for d in datasets if dataset_filter.lower() in d["name"].lower()]
            if not datasets:
                print(f"❌ No datasets match filter: {dataset_filter}")
                return {"error": f"No datasets match filter: {dataset_filter}"}
        
        # System information
        system_info = {
            "cpu_count": psutil.cpu_count(),
            "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 1),
            "python_version": sys.version,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Run benchmarks
        results = {
            "system_info": system_info,
            "datasets": []
        }
        
        print(f"Starting comprehensive benchmark on {len(datasets)} datasets")
        print(f"💻 System: {system_info['cpu_count']} cores, {system_info['memory_total_gb']} GB RAM")
        
        total_start = time.time()
        
        for dataset in datasets:
            try:
                dataset_result = self.benchmark_dataset(dataset)
                results["datasets"].append(dataset_result)
            except Exception as e:
                print(f"❌ Failed to benchmark {dataset['name']}: {e}")
                results["datasets"].append({
                    "dataset": dataset["name"],
                    "error": str(e)
                })
        
        total_time = time.time() - total_start
        results["total_benchmark_time_sec"] = round(total_time, 1)
        
        return results
    
    def generate_summary_report(self, results: Dict) -> str:
        """Generate a human-readable summary report"""
        
        if "error" in results:
            return f"Benchmark failed: {results['error']}"
        
        report = []
        report.append("=" * 60)
        report.append("LogReducer Performance Benchmark Report")
        report.append("=" * 60)
        
        # System info
        system = results["system_info"]
        report.append(f"System: {system['cpu_count']} CPU cores, {system['memory_total_gb']} GB RAM")
        report.append(f"Timestamp: {system['timestamp']}")
        report.append(f"Total benchmark time: {results['total_benchmark_time_sec']} seconds")
        report.append("")
        
        # Dataset results
        for dataset in results["datasets"]:
            if "error" in dataset:
                report.append(f"❌ {dataset['dataset']}: {dataset['error']}")
                continue
                
            report.append(f"📁 Dataset: {dataset['dataset']} ({dataset['file_size_mb']} MB)")
            report.append("-" * 50)
            
            # Find best performing configuration
            best_config = None
            best_throughput = 0
            
            for config in dataset["configurations"]:
                if "error" in config:
                    continue
                    
                throughput = config.get("throughput_mb_sec", 0)
                if throughput > best_throughput:
                    best_throughput = throughput
                    best_config = config
            
            if best_config:
                report.append(f"Best performance: {best_config['configuration']}")
                report.append(f"   Throughput: {best_config['throughput_mb_sec']} MB/sec")
                report.append(f"   Reduction:  {best_config['reduction_percent']}%")
                report.append(f"   Time:       {best_config['processing_time_sec']}s")
                report.append("")
            
            # Configuration details
            for config in dataset["configurations"]:
                if "error" in config:
                    report.append(f"   ❌ {config['configuration']}: {config['error']}")
                else:
                    report.append(f"   {config['configuration']:15} | "
                                f"{config['throughput_mb_sec']:6.1f} MB/s | "
                                f"{config['reduction_percent']:5.1f}% | "
                                f"{config['processing_time_sec']:6.1f}s | "
                                f"{config['memory_used_mb']:5.1f} MB")
            
            report.append("")
        
        return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(description="Run LogReducer performance benchmarks")
    parser.add_argument("--dataset", help="Filter datasets by name")
    parser.add_argument("--output", help="Save results to JSON file")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    project_root = Path(__file__).parent.parent
    runner = BenchmarkRunner(project_root)
    
    # Run benchmarks
    results = runner.run_comprehensive_benchmark(args.dataset)
    
    # Generate report
    report = runner.generate_summary_report(results)
    print("\n" + report)
    
    # Save results if requested
    if args.output:
        output_path = Path(args.output)
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nDetailed results saved to: {output_path}")
    
    # Also save to .tmp for reference
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    auto_output = project_root / ".tmp" / f"benchmark_results_{timestamp}.json"
    with open(auto_output, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"Results automatically saved to: {auto_output}")


if __name__ == "__main__":
    main()