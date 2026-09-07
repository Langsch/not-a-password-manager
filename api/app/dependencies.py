"""Shared route dependencies."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from fastapi import Request
from psycopg import AsyncConnection


async def db(request: Request) -> AsyncIterator[AsyncConnection[Any]]:
    """A connection from the pool, committed on success and rolled back on error."""
    async with request.app.state.pool.connection() as conn:
        yield conn
