"""Integration-test fixtures: real services, local-network first, docker fallback.

Each service fixture prefers a configured local/network endpoint (env vars,
typically loaded from the project ``.env`` - see .env.example). If none is
configured or reachable, it starts a throwaway docker container via
testcontainers and stops it the moment the session ends - nothing is left
running. If neither a local endpoint nor docker is available, dependent tests
skip rather than fail.
"""

from __future__ import annotations

import contextlib
import os
import time
from collections.abc import Iterator
from typing import Any

import pytest


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _env_first(*names: str, default: str = "") -> str:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return default


# ---------------------------------------------------------------------------
# ClickHouse
# ---------------------------------------------------------------------------


def _clickhouse_from_env() -> Any | None:
    """Return a connected clickhouse-connect client from env config, or None.

    Reads the CLICKHOUSE_* names (see .env.example). Returns None if unset
    or unreachable.
    """
    host = _env_first("CLICKHOUSE_HOST")
    if not host:
        return None
    try:
        import clickhouse_connect

        client = clickhouse_connect.get_client(
            host=host,
            port=int(_env_first("CLICKHOUSE_PORT", default="8123")),
            username=_env_first("CLICKHOUSE_USER", default="default"),
            password=_env_first("CLICKHOUSE_PASSWORD"),
            secure=_env_bool("CLICKHOUSE_SECURE"),
            verify=_env_bool("CLICKHOUSE_VERIFY", default=True),
            connect_timeout=5,
            send_receive_timeout=10,
        )
        client.command("SELECT 1")
        return client
    except Exception:
        return None


def _await_clickhouse_http(host: str, port: int, timeout: float = 45.0) -> Any:
    """Poll the HTTP interface until a query succeeds (real readiness signal)."""
    import clickhouse_connect

    deadline = time.monotonic() + timeout
    last_exc: Exception | None = None
    while time.monotonic() < deadline:
        try:
            client = clickhouse_connect.get_client(host=host, port=port, username="default", password="")
            client.command("SELECT 1")
            return client
        except Exception as exc:  # container HTTP not up yet - back off and retry
            last_exc = exc
            time.sleep(1.0)
    raise TimeoutError(f"ClickHouse HTTP not ready on {host}:{port}") from last_exc


def _clickhouse_from_docker() -> tuple[Any, Any] | None:
    """Start a throwaway ClickHouse container; return (client, container) or None.

    Uses a raw DockerContainer over the HTTP port so only clickhouse-connect is
    needed (no native clickhouse-driver). Readiness gates on the server's own
    "Ready for connections" log line plus a successful query.
    """
    try:
        from testcontainers.core.container import DockerContainer
        from testcontainers.core.waiting_utils import wait_for_logs
    except ImportError:
        return None
    try:
        container = DockerContainer("clickhouse/clickhouse-server:24.8").with_exposed_ports(8123)
        container.start()
        wait_for_logs(container, "Ready for connections", timeout=60)
    except Exception:
        with contextlib.suppress(Exception):
            container.stop()
        return None
    host = container.get_container_host_ip()
    port = int(container.get_exposed_port(8123))
    client = _await_clickhouse_http(host, port)
    return client, container


@pytest.fixture(scope="session")
def clickhouse_client() -> Iterator[Any]:
    """A ClickHouse client - local-network if configured, else docker, else skip."""
    client = _clickhouse_from_env()
    if client is not None:
        try:
            yield client
        finally:
            with contextlib.suppress(Exception):
                client.close()
        return

    docker = _clickhouse_from_docker()
    if docker is None:
        pytest.skip("no ClickHouse: set CLICKHOUSE_* in the local .env, or start Docker")
    client, container = docker
    try:
        yield client
    finally:
        with contextlib.suppress(Exception):
            client.close()
        container.stop()  # stop the fallback container as soon as we are done


# ---------------------------------------------------------------------------
# Kafka
# ---------------------------------------------------------------------------


def _kafka_from_env() -> str | None:
    """Return a reachable bootstrap.servers string from env, or None."""
    servers = _env_first("KAFKA_BOOTSTRAP_SERVERS")
    if not servers:
        return None
    try:
        from confluent_kafka.admin import AdminClient

        AdminClient({"bootstrap.servers": servers, "socket.timeout.ms": 3000}).list_topics(timeout=5)
        return servers
    except Exception:
        return None


def _kafka_from_docker() -> tuple[str, Any] | None:
    """Start a throwaway Kafka container; return (bootstrap, container) or None."""
    try:
        from testcontainers.kafka import KafkaContainer
    except ImportError:
        return None
    try:
        container = KafkaContainer()
        container.start()
    except Exception:
        with contextlib.suppress(Exception):
            container.stop()
        return None
    return container.get_bootstrap_server(), container


@pytest.fixture(scope="session")
def kafka_bootstrap() -> Iterator[str]:
    """A Kafka bootstrap string - local if configured, else docker, else skip."""
    servers = _kafka_from_env()
    if servers is not None:
        yield servers
        return

    docker = _kafka_from_docker()
    if docker is None:
        pytest.skip("no Kafka: set KAFKA_BOOTSTRAP_SERVERS, or start Docker")
    servers, container = docker
    try:
        yield servers
    finally:
        container.stop()  # stop the fallback container as soon as we are done


# ---------------------------------------------------------------------------
# SQL engines (PostgreSQL, MySQL) - throwaway docker containers, seeded once
# ---------------------------------------------------------------------------


def _seed_logs(engine: Any, rows: int) -> None:
    """Create a `logs` table with `rows` varied lines (read-only for sampling)."""
    from sqlalchemy import text

    is_mysql = engine.dialect.name in ("mysql", "mariadb")
    col = "VARCHAR(255)" if is_mysql else "TEXT"
    with engine.begin() as conn:
        conn.execute(text(f"CREATE TABLE logs (id INTEGER, line {col})"))
        conn.execute(
            text("INSERT INTO logs (id, line) VALUES (:i, :l)"),
            [{"i": i, "l": f"ERROR shard={i % 8} request failed req={i}"} for i in range(rows)],
        )


@pytest.fixture(scope="session")
def pg_logs_engine() -> Iterator[Any]:
    """A PostgreSQL engine with a seeded `logs` table (docker, else skip)."""
    try:
        from sqlalchemy import create_engine
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.skip("PostgreSQL integration deps not installed")
    try:
        container = PostgresContainer("postgres:16", driver="psycopg")
        container.start()
    except Exception as exc:  # no docker / image pull failed
        pytest.skip(f"no Docker for PostgreSQL: {exc}")
    engine = create_engine(container.get_connection_url())
    try:
        _seed_logs(engine, 5000)
        yield engine
    finally:
        with contextlib.suppress(Exception):
            engine.dispose()
        container.stop()


@pytest.fixture(scope="session")
def mysql_logs_engine() -> Iterator[Any]:
    """A MySQL engine with a seeded `logs` table (docker, else skip)."""
    try:
        from sqlalchemy import create_engine
        from testcontainers.mysql import MySqlContainer
    except ImportError:
        pytest.skip("MySQL integration deps not installed")
    try:
        container = MySqlContainer("mysql:8.4")
        container.start()
    except Exception as exc:  # no docker / image pull failed
        pytest.skip(f"no Docker for MySQL: {exc}")
    # Force the pymysql driver (the bare mysql:// URL defaults to MySQLdb, which
    # we do not install).
    url = container.get_connection_url()
    if url.startswith("mysql://"):
        url = url.replace("mysql://", "mysql+pymysql://", 1)
    engine = create_engine(url)
    try:
        _seed_logs(engine, 5000)
        yield engine
    finally:
        with contextlib.suppress(Exception):
            engine.dispose()
        container.stop()
