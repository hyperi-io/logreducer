"""ClickHouse input source for logreducer (optional ``clickhouse`` extra).

Streams log lines out of ClickHouse using the official ``clickhouse-connect``
driver's native block streaming (``query_row_block_stream``). ClickHouse returns
results in blocks; this iterates block by block and row by row, so memory stays
flat no matter how large the result is.

ClickHouse gets its own adapter rather than going through SQLAlchemy on purpose:
ClickHouse's SQLAlchemy dialect buffers the whole result client-side, which
defeats constant-memory streaming. The native driver's block interface is the
only path that streams. Everything else mirrors SQLSource - re-iterable (each
pass re-runs the query), first column is the log line, NULL/blank skipped.

Row -> line convention: the query selects the log line as its **first column**,
e.g. ``SELECT message FROM logs WHERE ...``.

Install: ``pip install 'logreducer[clickhouse]'``.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from clickhouse_connect.driver.client import Client

_INSTALL_HINT = "logreducer's ClickHouse source needs clickhouse-connect. Install the extra:\n    pip install 'logreducer[clickhouse]'"


class ClickHouseSource:
    """A re-iterable stream of log lines from a ClickHouse query.

    Each iteration opens a block stream and re-runs the query, so the reducer's
    multi-pass modes work. The first column of each row is the log line; NULLs
    and blank lines are skipped, matching FileSource.
    """

    def __init__(
        self,
        client_or_dsn: Client | str,
        query: str,
        *,
        parameters: dict[str, Any] | None = None,
        settings: dict[str, Any] | None = None,
    ) -> None:
        """Build a ClickHouse source.

        Args:
            client_or_dsn: A ``clickhouse-connect`` Client (borrowed, not
                closed) or a ``clickhouse://user:pass@host:port/db`` DSN string
                (a client is created and owned here).
            query: A SQL SELECT whose first column is the log line.
            parameters: Optional query parameters (server-side binding).
            settings: Optional ClickHouse settings for the query.
        """
        try:
            import clickhouse_connect
            from clickhouse_connect.driver.client import Client as _Client
        except ImportError as exc:  # pragma: no cover - exercised only without the extra
            raise ImportError(_INSTALL_HINT) from exc

        if isinstance(client_or_dsn, str):
            self._client = clickhouse_connect.get_client(dsn=client_or_dsn)
            self._owns_client = True
        elif isinstance(client_or_dsn, _Client):
            self._client = client_or_dsn
            self._owns_client = False
        else:
            raise TypeError(
                f"client_or_dsn must be a clickhouse-connect Client or a DSN string, got {type(client_or_dsn).__name__}"
            )

        self.query = query
        self.parameters = parameters
        self.settings = settings

    def __iter__(self) -> Iterator[str]:
        with self._client.query_row_block_stream(
            self.query, parameters=self.parameters, settings=self.settings
        ) as stream:
            for block in stream:
                for row in block:
                    value = row[0]
                    if value is None:
                        continue
                    line = str(value).strip()
                    if line:
                        yield line

    def close(self) -> None:
        """Close the client, but only if this source created it."""
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> ClickHouseSource:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"ClickHouseSource(query={self.query!r})"
