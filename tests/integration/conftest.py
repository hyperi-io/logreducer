"""Integration-test fixtures: real services, env-first, docker fallback.

The ClickHouse and Kafka fixtures prefer a configured endpoint (env vars,
typically loaded from the project ``.env`` - see .env.example) and fall back to
a throwaway docker container; PostgreSQL and MySQL are docker-only (they exist
solely to exercise per-dialect sampling). Containers are stopped the moment the
session ends unless LOGREDUCER_KEEP_CONTAINERS=1. If neither an endpoint nor
docker is available, dependent tests skip rather than fail.
"""

from __future__ import annotations

import contextlib
import os
import time
from collections.abc import Iterator
from typing import Any

import pytest


def _prefixed(names: tuple[str, ...]) -> tuple[str, ...]:
    """Expand names with the optional env-prefix cascade.

    LOGREDUCER_ENV_PREFIX="DFE" makes DFE_CLICKHOUSE_HOST win over
    CLICKHOUSE_HOST (prefixed first, bare fallback) - the scalo config-cascade
    convention, so a .env written for another project (e.g. dfe-engine's
    DFE_* names) drops in without renaming.
    """
    prefix = os.environ.get("LOGREDUCER_ENV_PREFIX", "").strip().rstrip("_")
    if not prefix:
        return names
    expanded: list[str] = []
    for name in names:
        expanded.append(f"{prefix}_{name}")
        expanded.append(name)
    return tuple(expanded)


def _env_bool(name: str, default: bool = False) -> bool:
    for candidate in _prefixed((name,)):
        value = os.environ.get(candidate)
        if value is not None:
            return value.strip().lower() in ("1", "true", "yes", "on")
    return default


def _env_first(*names: str, default: str = "") -> str:
    for name in _prefixed(names):
        value = os.environ.get(name)
        if value:
            return value
    return default


def _keep_containers() -> bool:
    """LOGREDUCER_KEEP_CONTAINERS=1 leaves docker services RUNNING after the run.

    Default is to stop/remove them. Keeping them lets you re-run fast: grab the
    printed endpoint and export it (KAFKA_BOOTSTRAP_SERVERS / CLICKHOUSE_* / a
    DB URL) so the next run takes the env-first path and skips container startup.
    """
    return os.environ.get("LOGREDUCER_KEEP_CONTAINERS", "").strip().lower() in ("1", "true", "yes", "on")


def _stop(container: Any, label: str, endpoint: str) -> None:
    """Stop a throwaway container, unless the caller asked to keep it running."""
    if _keep_containers():
        print(f"\n[keep] {label} left running at {endpoint} (LOGREDUCER_KEEP_CONTAINERS=1)")
        return
    with contextlib.suppress(Exception):
        container.stop()


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
    except Exception as exc:
        # Say WHY the configured endpoint was skipped - a typo'd password
        # silently falling back to docker is painful to debug.
        print(f"\n[env] CLICKHOUSE_HOST={host} configured but unusable ({exc}); falling back to docker")
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
        container = DockerContainer("clickhouse/clickhouse-server:24.8.14").with_exposed_ports(8123)
        container.start()
        wait_for_logs(container, "Ready for connections", timeout=60)
        # Inside the try: if the HTTP probe times out, the container must
        # still be stopped rather than leaked as a fixture ERROR.
        host = container.get_container_host_ip()
        port = int(container.get_exposed_port(8123))
        client = _await_clickhouse_http(host, port)
    except Exception:
        with contextlib.suppress(Exception):
            container.stop()
        return None
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
        endpoint = f"{container.get_container_host_ip()}:{container.get_exposed_port(8123)}"
        _stop(container, "ClickHouse", endpoint)


# ---------------------------------------------------------------------------
# Kafka
# ---------------------------------------------------------------------------


def _kafka_config_from_env() -> str | dict[str, Any] | None:
    """Return a reachable Kafka config from env, or None.

    A bare ``KAFKA_BOOTSTRAP_SERVERS`` yields a plain bootstrap string. Adding
    ``KAFKA_SECURITY_PROTOCOL`` (e.g. SASL_SSL) upgrades it to a full librdkafka
    config dict (SASL mechanism/username/password + TLS CA) - used to reach the
    authenticated PET broker. Probed with an AdminClient before use.
    """
    servers = _env_first("KAFKA_BOOTSTRAP_SERVERS")
    if not servers:
        return None
    protocol = _env_first("KAFKA_SECURITY_PROTOCOL")
    config: str | dict[str, Any]
    if protocol:
        config = {"bootstrap.servers": servers, "security.protocol": protocol}
        for env_key, conf_key in (
            ("KAFKA_SASL_MECHANISM", "sasl.mechanism"),
            ("KAFKA_SASL_USERNAME", "sasl.username"),
            ("KAFKA_SASL_PASSWORD", "sasl.password"),
            ("KAFKA_SSL_CA_LOCATION", "ssl.ca.location"),
        ):
            value = _env_first(env_key)
            if value:
                config[conf_key] = value
        # Internal PET broker: skip TLS cert verification (same stance as
        # CLICKHOUSE_VERIFY=false) - the chain uses an internal, pre-rebrand CA.
        if not _env_bool("KAFKA_SSL_VERIFY", default=True):
            config["enable.ssl.certificate.verification"] = "false"
    else:
        config = servers
    try:
        from confluent_kafka.admin import AdminClient

        probe = dict(config) if isinstance(config, dict) else {"bootstrap.servers": config}
        probe["socket.timeout.ms"] = 6000
        AdminClient(probe).list_topics(timeout=8)
        return config
    except Exception as exc:
        # Say WHY the configured broker was skipped rather than silently
        # falling back to docker (bad SASL creds look identical otherwise).
        print(f"\n[env] KAFKA_BOOTSTRAP_SERVERS={servers} configured but unusable ({exc}); falling back to docker")
        return None


def _redpanda_from_docker() -> tuple[str, Any] | None:
    """Start a throwaway Redpanda container; return (bootstrap, container) or None.

    Redpanda is the docker broker (Kafka-API compatible, single binary, far
    smaller/faster to start than Apache Kafka) - confluent-kafka talks to it
    unchanged.
    """
    try:
        from testcontainers.kafka import RedpandaContainer
    except ImportError:
        return None
    try:
        container = RedpandaContainer()
        container.start()
    except Exception:
        with contextlib.suppress(Exception):
            container.stop()
        return None
    return container.get_bootstrap_server(), container


@pytest.fixture(scope="session")
def kafka_bootstrap() -> Iterator[str | dict[str, Any]]:
    """A Kafka config - a configured broker (str, or a SASL dict for PET) if
    reachable, else a Redpanda docker broker (str), else skip.

    The value is accepted directly by KafkaSource/KafkaSink and the corpora
    loaders (all take a bootstrap string or a full librdkafka config dict).
    """
    config = _kafka_config_from_env()
    if config is not None:
        yield config
        return

    docker = _redpanda_from_docker()
    if docker is None:
        pytest.skip("no Kafka broker: set KAFKA_BOOTSTRAP_SERVERS, or start Docker (Redpanda)")
    servers, container = docker
    try:
        yield servers
    finally:
        _stop(container, "Redpanda", servers)


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
def pg_engine() -> Iterator[Any]:
    """A bare PostgreSQL engine on a throwaway container (docker, else skip)."""
    try:
        from sqlalchemy import create_engine
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.skip("PostgreSQL integration deps not installed")
    try:
        container = PostgresContainer("postgres:16.6", driver="psycopg")
        container.start()
    except Exception as exc:  # no docker / image pull failed
        pytest.skip(f"no Docker for PostgreSQL: {exc}")
    engine = create_engine(container.get_connection_url())
    try:
        yield engine
    finally:
        with contextlib.suppress(Exception):
            engine.dispose()
        _stop(container, "PostgreSQL", container.get_connection_url())


@pytest.fixture(scope="session")
def mysql_engine() -> Iterator[Any]:
    """A bare MySQL engine on a throwaway container (docker, else skip)."""
    try:
        from sqlalchemy import create_engine
        from testcontainers.mysql import MySqlContainer
    except ImportError:
        pytest.skip("MySQL integration deps not installed")
    try:
        container = MySqlContainer("mysql:8.4.5")
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
        yield engine
    finally:
        with contextlib.suppress(Exception):
            engine.dispose()
        _stop(container, "MySQL", url)


@pytest.fixture(scope="session")
def pg_logs_engine(pg_engine: Any) -> Any:
    """PostgreSQL with a seeded synthetic `logs` table (for the sampling tests)."""
    _seed_logs(pg_engine, 5000)
    return pg_engine


@pytest.fixture(scope="session")
def mysql_logs_engine(mysql_engine: Any) -> Any:
    """MySQL with a seeded synthetic `logs` table (for the sampling tests)."""
    _seed_logs(mysql_engine, 5000)
    return mysql_engine
