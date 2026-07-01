"""
PyTest configuration and shared fixtures
"""

import random
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# Load the local .env (CLICKHOUSE_*, KAFKA_BOOTSTRAP_SERVERS, ...) so the
# integration tests can reach a real local-network service when one is
# configured. An absent or empty .env is fine - those tests then fall back to a
# throwaway docker container, or skip if docker is unavailable too.
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:  # python-dotenv is a test-only dep; absence just means no .env load
    pass


@pytest.fixture(scope="session")
def test_data_dir():
    """Create temporary directory for test data"""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir) / "test_data"
        test_dir.mkdir(exist_ok=True)
        yield test_dir


@pytest.fixture
def sample_log_lines():
    """Generate sample log lines for testing"""
    return [
        "2024-01-01 12:00:00 INFO Application started",
        "2024-01-01 12:00:01 INFO User alice logged in from 192.168.1.100",
        "2024-01-01 12:00:02 ERROR Database connection failed to prod-db-01",
        "2024-01-01 12:00:03 INFO User bob logged in from 192.168.1.101",
        "2024-01-01 12:00:04 WARN Memory usage at 85% for auth service",
        "2024-01-01 12:00:05 INFO Processing request req_001234 with params user=charlie",
        "2024-01-01 12:00:06 ERROR Authentication failed for user eve",
        "2024-01-01 12:00:07 INFO Application started",
        "2024-01-01 12:00:08 WARN Slow query detected: 1500ms for query 'SELECT * FROM users'",
        "2024-01-01 12:00:09 INFO User dave logged in from 192.168.1.102",
    ]


@pytest.fixture
def small_log_file(test_data_dir, sample_log_lines) -> Path:
    """Create a small log file for testing"""
    log_file = test_data_dir / "small_test.log"
    with open(log_file, "w") as f:
        for line in sample_log_lines:
            f.write(line + "\n")
    return log_file


@pytest.fixture
def medium_log_file(test_data_dir) -> Path:
    """Create a medium-sized log file for testing"""
    log_file = test_data_dir / "medium_test.log"

    log_templates = [
        "INFO User {} logged in from {}",
        "INFO Processing request {} with parameters {}",
        "INFO Database query completed in {}ms",
        "WARN Connection timeout for service {}",
        "WARN Memory usage at {}% for service {}",
        "ERROR Database connection failed to {}",
        "ERROR Authentication failed for user {}",
        "CRITICAL System running out of memory",
        "DEBUG Cache hit for key {}",
        "DEBUG Request completed successfully",
    ]

    users = ["alice", "bob", "charlie", "dave", "eve"]
    services = ["auth", "db", "api", "cache"]

    start_time = datetime(2024, 1, 1, 12, 0, 0)

    with open(log_file, "w") as f:
        for i in range(1000):
            timestamp = start_time + timedelta(seconds=i)
            template = random.choice(log_templates)

            # Fill template based on content
            if "{}" in template:
                if "User" in template and "logged in" in template:
                    user = random.choice(users)
                    ip = f"192.168.1.{random.randint(100, 200)}"
                    line = template.format(user, ip)
                elif "request" in template:
                    req_id = f"req_{i:06d}"
                    params = f"user={random.choice(users)}"
                    line = template.format(req_id, params)
                elif "query completed" in template:
                    ms = random.randint(10, 1000)
                    line = template.format(ms)
                elif "Memory usage" in template:
                    percentage = random.randint(60, 95)
                    service = random.choice(services)
                    line = template.format(percentage, service)
                elif "service" in template or "user" in template:
                    value = random.choice(users + services)
                    line = template.format(value)
                elif "key" in template:
                    key = f"cache_key_{random.randint(1000, 9999)}"
                    line = template.format(key)
                else:
                    line = template.format(f"item_{i}")
            else:
                line = template

            f.write(f"{timestamp.strftime('%Y-%m-%d %H:%M:%S')} {line}\n")

    return log_file


@pytest.fixture
def large_log_file(test_data_dir) -> Path:
    """Create a large log file for integration testing"""
    log_file = test_data_dir / "large_test.log"

    # Generate more complex log patterns
    with open(log_file, "w") as f:
        start_time = datetime(2024, 1, 1, 12, 0, 0)

        for i in range(10000):  # 10k lines for integration tests
            timestamp = start_time + timedelta(seconds=i // 10)  # More realistic timing

            # Create more realistic log patterns
            if i % 100 == 0:
                # Periodic system messages
                f.write(f"{timestamp.strftime('%Y-%m-%d %H:%M:%S')} INFO System health check passed\n")
            elif i % 1000 == 0:
                # Rare critical events
                f.write(f"{timestamp.strftime('%Y-%m-%d %H:%M:%S')} CRITICAL Memory spike detected\n")
            elif i % 50 == 0:
                # Regular errors
                f.write(f"{timestamp.strftime('%Y-%m-%d %H:%M:%S')} ERROR Connection timeout to service-{i % 5}\n")
            else:
                # Normal operations
                level = random.choice(["INFO", "DEBUG", "WARN"])
                action = random.choice(["processed", "completed", "started", "finished"])
                item = f"task_{i:06d}"
                f.write(f"{timestamp.strftime('%Y-%m-%d %H:%M:%S')} {level} Operation {action} for {item}\n")

    return log_file
