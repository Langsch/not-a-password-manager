"""FastAPI application entrypoint.

Owns the lifespan: the PostgreSQL pool opens on startup and closes on shutdown.
Mounts the routers under /api/v1 and registers the error envelope.

Migrations are *not* run here. ``alembic upgrade head`` is a separate command,
so two instances starting at once cannot race each other through the same
revisions.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import auth, health
from app.config import get_settings
from app.db.pool import create_pool
from app.errors import register_error_handlers

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    pool = create_pool(get_settings().database_url)
    await pool.open(wait=True)
    app.state.pool = pool
    try:
        yield
    finally:
        await pool.close()


app = FastAPI(
    title="not-a-password-manager",
    description="A self-hosted password notebook.",
    version="0.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

register_error_handlers(app)
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(health.router, prefix=API_PREFIX)
