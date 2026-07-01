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
    ) -> None:
        """Build a SQL source.

        Args:
            connectable: A SQLAlchemy ``Engine`` (borrowed, not disposed) or a
                database URL string (an engine is created and owned here).
            query: A SQL SELECT whose first column is the log line.
            params: Optional bound parameters for the query.
            yield_per: Server-side cursor batch size (rows fetched per round
                trip). Larger trades memory for fewer round trips.
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

    def __iter__(self) -> Iterator[str]:
        from sqlalchemy import text

        stmt = text(self.query)
        with self._engine.connect() as conn:
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
