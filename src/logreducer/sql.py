"""SQL input source for logreducer (optional ``sql`` extra).

Streams log lines out of any SQL database SQLAlchemy can reach - PostgreSQL,
MySQL, SQLite, and the rest - using a server-side cursor (the ``yield_per``
execution option, which turns on ``stream_results``). Rows are pulled in
batches, so memory stays flat regardless of how many rows the query returns;
the reducer never holds the whole result set.

This is a thin convenience over the abstraction, not a data-access layer. An
application that already has a SQLAlchemy ``Engine`` passes it straight in and
keeps ownership of it; the package only borrows a connection per pass. A URL
string is also accepted for CLI use, in which case the engine is created and
owned here (call ``close()`` or use the source as a context manager to dispose
it).

Row -> line convention: the query selects the log line as its **first column**.
Anything else (levels, timestamps) should be folded into that column in SQL,
e.g. ``SELECT ts || ' ' || msg AS line FROM events``.

SQLAlchemy is the deliberate choice here: it is the only mature *cross-database*
Python layer that streams via server-side cursors. Single-database drivers
(asyncpg, psycopg) or columnar loaders (ConnectorX, Polars) either lock to one
backend or materialise the entire result - the memory hazard this avoids.

Install: ``pip install 'logreducer[sql]'`` plus your database's DBAPI driver
(``psycopg`` for PostgreSQL, ``PyMySQL`` for MySQL; SQLite needs none).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

_INSTALL_HINT = (
    "logreducer's SQL source needs SQLAlchemy. Install the extra:\n"
    "    pip install 'logreducer[sql]'\n"
    "plus your database's DBAPI driver (psycopg for PostgreSQL, PyMySQL for "
    "MySQL; SQLite needs none)."
)


class SQLSource:
    """A re-iterable stream of log lines from a SQL query.

    Each iteration opens a fresh connection and re-runs the query with a
    server-side cursor, so the reducer's multi-pass modes work (every pass is
    an idempotent re-read). The first column of each row is the log line;
    NULLs and blank lines are skipped, matching FileSource.
    """

    def __init__(
        self,
        connectable: Engine | str,
        query: str,
        *,
        params: dict[str, Any] | None = None,
        yield_per: int = 1000,
        sample: float | None = None,
        sample_seed: int | None = None,
    ) -> None:
        """Build a SQL source.

        Args:
            connectable: A SQLAlchemy ``Engine`` (borrowed, not disposed) or a
                database URL string (an engine is created and owned here).
            query: A SQL SELECT whose first column is the log line.
            params: Optional bound parameters for the query.
            yield_per: Server-side cursor batch size (rows fetched per round
                trip). Larger trades memory for fewer round trips.
            sample: Optional fraction in (0, 1] - return only that fraction of
                rows via a per-dialect random predicate. Pass ``sample_seed``
                for a deterministic, re-iterable sample (required for the
                reducer's multi-pass modes; PostgreSQL/MySQL only). Without a
                seed the sample is best-effort and not reproducible across passes.
            sample_seed: Seed for a reproducible sample. Raises
                ``SamplingNotSupported`` on engines with no seedable RNG (SQLite).
        """
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.engine import Engine as _Engine
        except ImportError as exc:  # pragma: no cover - exercised only without the extra
            raise ImportError(_INSTALL_HINT) from exc

        if isinstance(connectable, str):
            self._engine = create_engine(connectable)
            self._owns_engine = True
        elif isinstance(connectable, _Engine):
            self._engine = connectable
            self._owns_engine = False
        else:
            raise TypeError(
                f"connectable must be a SQLAlchemy Engine or a URL string, got {type(connectable).__name__}"
            )

        self.query = query
        self.params = params
        self.yield_per = yield_per
        self.sample = sample
        self.sample_seed = sample_seed

        # Precompute the sampled SQL now so an unsupported request (e.g. a seed
        # on SQLite) fails at construction, not deep inside iteration.
        self._sample_setup: str | None = None
        self._sample_sql: str | None = None
        if sample is not None:
            from .sampling import build_sample_sql

            self._sample_setup, self._sample_sql = build_sample_sql(
                self._engine.dialect.name, query, sample, sample_seed
            )

    def __iter__(self) -> Iterator[str]:
        from sqlalchemy import text

        stmt = text(self._sample_sql if self._sample_sql is not None else self.query)
        with self._engine.connect() as conn:
            # A deterministic sample (PostgreSQL) needs its per-connection seed
            # set before the query, on the same connection.
            if self._sample_setup is not None:
                conn.exec_driver_sql(self._sample_setup)
            # yield_per implies stream_results: a server-side cursor fetching
            # `yield_per` rows per round trip, so memory does not grow with the
            # result size.
            result = conn.execution_options(yield_per=self.yield_per).execute(stmt, self.params or {})
            for row in result:
                value = row[0]
                if value is None:
                    continue
                line = str(value).strip()
                if line:
                    yield line

    def sample_batch(self, n: int) -> list[str]:
        """Return one fresh random batch of up to ``n`` log lines.

        Each call runs ``ORDER BY <rand> LIMIT n`` over the query, so successive
        calls draw different rows (with-replacement) - the primitive the
        ``reduce_to_target`` loop pulls batches from. Not re-iterable; a one-off
        list, not a streaming pass.
        """
        from sqlalchemy import text

        from .sampling import build_sample_batch_sql

        sql = build_sample_batch_sql(self._engine.dialect.name, self.query, n)
        out: list[str] = []
        with self._engine.connect() as conn:
            for row in conn.execute(text(sql), self.params or {}):
                value = row[0]
                if value is None:
                    continue
                line = str(value).strip()
                if line:
                    out.append(line)
        return out

    def close(self) -> None:
        """Dispose the engine, but only if this source created it."""
        if self._owns_engine:
            self._engine.dispose()

    def __enter__(self) -> SQLSource:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"SQLSource({self._engine.url!r}, query={self.query!r})"
