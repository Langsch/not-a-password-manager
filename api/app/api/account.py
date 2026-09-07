"""Account endpoints that act on the signed-in user."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.core.change_password import change_password
from app.dependencies import Caller, Db
from app.schemas.auth import ChangePasswordRequest

router = APIRouter(prefix="/account", tags=["account"])


@router.put("/password", status_code=status.HTTP_204_NO_CONTENT)
async def update_password(payload: ChangePasswordRequest, caller: Caller, conn: Db) -> Response:
    await change_password(
        conn,
        user_id=caller,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
