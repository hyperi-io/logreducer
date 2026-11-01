"""Integration-test fixtures: real services, never mocks.

ClickHouse and Kafka are the run's shared services from scalo's test plugin (loaded in the
root ``conftest.py``): one container each, shared by every xdist worker, or the pet the
``HYPERI_TEST_*`` settings name. Each test gets a database or topics of its own. PostgreSQL
and MySQL, which the plugin does not provide, are throwaway testcontainers stopped when the
session ends unless LOGREDUCER_KEEP_CONTAINERS=1, and skip without Docker.
"""

import contextlib
import os
from collections.abc import Iterator
from typing import Any

import pytest


def _keep_containers() -> bool:
    """LOGREDUCER_KEEP_CONTAINERS=1 leaves the PostgreSQL and MySQL containers RUNNING after the run."""
    return os.environ.get("LOGREDUCER_KEEP_CONTAINERS", "").strip().lower() in ("1", "true", "yes", "on")


def _stop(container: Any, label: str, endpoint: str) -> None:
    """Stop a throwaway container, unless the caller asked to keep it running."""
    if _keep_containers():
        print(f"\n[keep] {label} left running at {endpoint} (LOGREDUCER_KEEP_CONTAINERS=1)")
        return
    with contextlib.suppress(Exception):
        container.stop()


# ---------------------------------------------------------------------------
# ClickHouse and Kafka - the run's shared services
# ---------------------------------------------------------------------------


@pytest.fixture
def clickhouse_client(shared_clickhouse: Any, clickhouse_database: str) -> Iterator[Any]:
    """A clickhouse-connect client on the run's ClickHouse, in a database of this test's own."""
    import clickhouse_connect

    options: dict[str, Any] = {"secure": shared_clickhouse.secure}
    if shared_clickhouse.ca_file:
        options["ca_cert"] = shared_clickhouse.ca_file
    client = clickhouse_connect.get_client(
        host=shared_clickhouse.host,
        port=shared_clickhouse.http_port,
        username=shared_clickhouse.user,
        password=shared_clickhouse.password,
        database=clickhouse_database,
        **options,
    )
    try:
        yield client
    finally:
        client.close()


@pytest.fixture
def kafka_bootstrap(shared_kafka: Any) -> dict[str, Any]:
    """The librdkafka config for the run's Kafka, security settings included.

    Topic auto-create is off there, so a test makes its topics with ``kafka_topics``.
    """
    return dict(shared_kafka.client_config)


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
        from testcontainers.community.postgres import PostgresContainer
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
        from testcontainers.community.mysql import MySqlContainer
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
