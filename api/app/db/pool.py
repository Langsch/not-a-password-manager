"""The PostgreSQL connection pool.

Created closed so the caller decides when to connect; ``app.main`` opens it on
startup and closes it on shutdown.
"""

from __future__ import annotations

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool


def create_pool(dsn: str) -> AsyncConnectionPool:
    return AsyncConnectionPool(
        dsn,
        min_size=1,
        max_size=10,
        open=False,
        kwargs={"row_factory": dict_row},
    )
