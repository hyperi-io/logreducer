"""
Optional usage analytics and telemetry for LogReducer

Provides privacy-focused telemetry to understand real-world usage patterns.
All telemetry is:
- Completely optional (disabled by default)
- Anonymous (no PII collected)
- Transparent (logs what it sends)
- User-controlled (easy to disable)
"""

import hashlib
import json
import os
import platform
import time
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Optional, Any
import threading

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


@dataclass
class TelemetryEvent:
    """A single telemetry event"""
    event_type: str
    timestamp: float
    session_id: str
    version: str
    system_info: Dict[str, Any]
    performance_metrics: Dict[str, Any]
    configuration: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


class TelemetryCollector:
    """Collects and sends optional usage analytics"""
    
    def __init__(self, enabled: bool = False, 
                 endpoint: Optional[str] = None,
                 local_only: bool = True):
        """
        Initialize telemetry collector
        
        Args:
            enabled: Whether telemetry is enabled
            endpoint: Custom telemetry endpoint URL
            local_only: If True, only save locally (no network calls)
        """
        self.enabled = enabled and self._user_opted_in()
        self.endpoint = endpoint or os.getenv("LOGREDUCER_TELEMETRY_ENDPOINT")
        self.local_only = local_only or not REQUESTS_AVAILABLE
        
        # Generate anonymous session ID
        self.session_id = str(uuid.uuid4())
        
        # Local storage for telemetry data
        self.telemetry_dir = Path.home() / ".logreducer" / "telemetry"
        if self.enabled:
            self.telemetry_dir.mkdir(parents=True, exist_ok=True)
        
        # Thread-safe event queue
        self._event_queue = []
        self._queue_lock = threading.Lock()
        
    def _user_opted_in(self) -> bool:
        """Check if user has explicitly opted into telemetry"""
        # Check environment variable
        env_opt_in = os.getenv("LOGREDUCER_TELEMETRY_ENABLED", "").lower()
        if env_opt_in in ("1", "true", "yes", "on"):
            return True
            
        # Check opt-in file
        opt_in_file = Path.home() / ".logreducer" / "telemetry_opt_in"
        return opt_in_file.exists()
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get anonymous system information"""
        # Hash hostname for privacy
        hostname_hash = hashlib.sha256(
            platform.node().encode()
        ).hexdigest()[:8]
        
        return {
            "platform": platform.system(),
            "platform_version": platform.release(),
            "python_version": platform.python_version(),
            "architecture": platform.machine(),
            "hostname_hash": hostname_hash,
            "cpu_count": os.cpu_count(),
            "container_detected": self._detect_container()
        }
    
    def _detect_container(self) -> bool:
        """Detect if running in a container"""
        # Check for common container indicators
        container_indicators = [
            Path("/.dockerenv").exists(),
            Path("/proc/1/cgroup").exists() and 
            "docker" in Path("/proc/1/cgroup").read_text(errors="ignore"),
            os.getenv("KUBERNETES_SERVICE_HOST") is not None,
            os.getenv("DOCKER_CONTAINER") is not None
        ]
        return any(container_indicators)
    
    def record_processing_event(self, 
                               file_size_mb: float,
                               processing_time_sec: float,
                               reduction_percent: float,
                               processing_mode: str,
                               processing_level: str,
                               memory_used_mb: float,
                               error: Optional[str] = None) -> None:
        """Record a log processing event"""
        
        if not self.enabled:
            return
            
        try:
            from . import __version__
            version = __version__
        except ImportError:
            version = "unknown"
        
        event = TelemetryEvent(
            event_type="processing_completed" if not error else "processing_error",
            timestamp=time.time(),
            session_id=self.session_id,
            version=version,
            system_info=self._get_system_info(),
            performance_metrics={
                "file_size_mb": round(file_size_mb, 2),
                "processing_time_sec": round(processing_time_sec, 2),
                "reduction_percent": round(reduction_percent, 1),
                "memory_used_mb": round(memory_used_mb, 1),
                "throughput_mb_sec": round(file_size_mb / processing_time_sec, 1) 
                                   if processing_time_sec > 0 else 0,
                "error": error
            },
            configuration={
                "processing_mode": processing_mode,
                "processing_level": processing_level,
                "container_environment": self._detect_container()
            }
        )
        
        self._queue_event(event)
    
    def record_cli_usage(self, command_args: Dict[str, Any]) -> None:
        """Record CLI command usage (anonymized)"""
        
        if not self.enabled:
            return
            
        try:
            from . import __version__
            version = __version__
        except ImportError:
            version = "unknown"
        
        # Sanitize arguments (remove file paths and personal info)
        sanitized_args = {}
        for key, value in command_args.items():
            if key in ["input_file", "output", "log_file"]:
                # Just record that these options were used, not the values
                sanitized_args[f"{key}_used"] = value is not None
            elif key in ["level", "mode", "format", "log_level"]:
                sanitized_args[key] = value
            elif key in ["estimate", "stats", "pretty_json", "log"]:
                sanitized_args[key] = bool(value)
        
        event = TelemetryEvent(
            event_type="cli_usage",
            timestamp=time.time(),
            session_id=self.session_id,
            version=version,
            system_info=self._get_system_info(),
            performance_metrics={},
            configuration=sanitized_args
        )
        
        self._queue_event(event)
    
    def _queue_event(self, event: TelemetryEvent) -> None:
        """Add event to processing queue"""
        with self._queue_lock:
            self._event_queue.append(event)
            
        # Save locally immediately
        self._save_event_locally(event)
        
        # Send to endpoint if configured (async)
        if not self.local_only and self.endpoint:
            threading.Thread(
                target=self._send_event,
                args=(event,),
                daemon=True
            ).start()
    
    def _save_event_locally(self, event: TelemetryEvent) -> None:
        """Save event to local file"""
        if not self.enabled:
            return
            
        try:
            timestamp = time.strftime("%Y%m%d", time.localtime(event.timestamp))
            log_file = self.telemetry_dir / f"telemetry_{timestamp}.jsonl"
            
            with open(log_file, 'a') as f:
                json.dump(event.to_dict(), f)
                f.write('\n')
                
        except Exception:
            # Silently fail - telemetry should never break the main application
            pass
    
    def _send_event(self, event: TelemetryEvent) -> None:
        """Send event to telemetry endpoint"""
        if not REQUESTS_AVAILABLE or not self.endpoint:
            return
            
        try:
            response = requests.post(
                self.endpoint,
                json=event.to_dict(),
                timeout=5,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
        except Exception:
            # Silently fail - telemetry should never break the main application
            pass
    
    def flush_events(self) -> None:
        """Flush any pending events"""
        if not self.enabled:
            return
            
        # Wait for background threads to complete
        # In practice, events are sent immediately, so this is mostly a no-op
        pass
    
    def get_local_stats(self) -> Dict[str, Any]:
        """Get statistics from locally stored telemetry"""
        if not self.enabled or not self.telemetry_dir.exists():
            return {"enabled": False}
        
        stats = {
            "enabled": True,
            "total_events": 0,
            "event_types": {},
            "date_range": []
        }
        
        try:
            for log_file in self.telemetry_dir.glob("telemetry_*.jsonl"):
                with open(log_file, 'r') as f:
                    for line in f:
                        try:
                            event = json.loads(line.strip())
                            stats["total_events"] += 1
                            
                            event_type = event.get("event_type", "unknown")
                            stats["event_types"][event_type] = \
                                stats["event_types"].get(event_type, 0) + 1
                                
                        except json.JSONDecodeError:
                            continue
                            
                # Extract date from filename
                date_part = log_file.name.replace("telemetry_", "").replace(".jsonl", "")
                if date_part not in stats["date_range"]:
                    stats["date_range"].append(date_part)
                    
            stats["date_range"].sort()
            
        except Exception:
            pass
            
        return stats


# Global telemetry collector instance
_global_collector: Optional[TelemetryCollector] = None


def get_telemetry_collector(enabled: bool = False, 
                          endpoint: Optional[str] = None,
                          local_only: bool = True) -> TelemetryCollector:
    """Get the global telemetry collector instance"""
    global _global_collector
    
    if _global_collector is None:
        _global_collector = TelemetryCollector(enabled, endpoint, local_only)
        
    return _global_collector


def opt_in_telemetry() -> None:
    """Opt user into telemetry collection"""
    opt_in_file = Path.home() / ".logreducer" / "telemetry_opt_in"
    opt_in_file.parent.mkdir(parents=True, exist_ok=True)
    opt_in_file.write_text(f"Opted in on {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    print("✅ Opted into LogReducer usage analytics")


def opt_out_telemetry() -> None:
    """Opt user out of telemetry collection"""
    opt_in_file = Path.home() / ".logreducer" / "telemetry_opt_in"
    if opt_in_file.exists():
        opt_in_file.unlink()
    print("✅ Opted out of LogReducer usage analytics")


def show_telemetry_status() -> None:
    """Show current telemetry status"""
    collector = get_telemetry_collector()
    stats = collector.get_local_stats()
    
    print("LogReducer Telemetry Status")
    print("=" * 30)
    print(f"Enabled: {'Yes' if stats['enabled'] else 'No'}")
    
    if stats["enabled"]:
        print(f"Total events recorded: {stats['total_events']}")
        if stats["event_types"]:
            print("Event types:")
            for event_type, count in stats["event_types"].items():
                print(f"  {event_type}: {count}")
        if stats["date_range"]:
            print(f"Data range: {stats['date_range'][0]} to {stats['date_range'][-1]}")
        
        telemetry_dir = Path.home() / ".logreducer" / "telemetry"
        print(f"Local data stored in: {telemetry_dir}")
    else:
        print("No telemetry data collected")
        print("To opt in: export LOGREDUCER_TELEMETRY_ENABLED=1")
        print("Or run: python -c 'from logreducer.telemetry import opt_in_telemetry; opt_in_telemetry()'")


if __name__ == "__main__":
    # CLI for telemetry management
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        if command == "opt-in":
            opt_in_telemetry()
        elif command == "opt-out":
            opt_out_telemetry()
        elif command == "status":
            show_telemetry_status()
        else:
            print("Usage: python -m logreducer.telemetry {opt-in|opt-out|status}")
    else:
        show_telemetry_status()