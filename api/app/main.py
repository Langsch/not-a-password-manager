"""FastAPI application entrypoint.

Holds nothing but the application object for now. The lifespan that opens the
PostgreSQL pool arrives with ``feat/database``; the error envelope and
``GET /health`` arrive with ``feat/health-and-errors``.

Migrations are *not* run from here. ``alembic upgrade head`` is a separate
command, so two instances starting at once cannot race each other through the
same revisions.
"""

from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(
    title="not-a-password-manager",
    description="A self-hosted password notebook.",
    version="0.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)
