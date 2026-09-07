"""Liveness: the service is up and can reach the database."""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(tags=["operations"])

# Short on purpose. A health check that hangs is worse than one that fails: the
# caller is asking whether the database is reachable *now*, not waiting for the
# pool to exhaust its own patience.
CONNECT_TIMEOUT_SECONDS = 2.0


@router.get("/health")
async def health(request: Request) -> dict[str, str]:
    async with request.app.state.pool.connection(timeout=CONNECT_TIMEOUT_SECONDS) as conn:
        await conn.execute("SELECT 1")
    return {"status": "ok"}
