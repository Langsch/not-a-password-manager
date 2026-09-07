"""Item endpoints."""

from __future__ import annotations

import math
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.core.create_item import create_item
from app.core.delete_item import delete_item
from app.core.list_items import list_items
from app.core.reveal_item import reveal_item
from app.core.update_item import update_item
from app.dependencies import Caller, Crypto, Db
from app.schemas.items import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    CreatedItem,
    CreateItemRequest,
    ItemPage,
    ItemSummary,
    PageMeta,
    RevealedSecrets,
    RevealRequest,
    UpdateItemRequest,
)

router = APIRouter(prefix="/items", tags=["items"])

Page = Annotated[int, Query(ge=1)]
PerPage = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)]
Search = Annotated[str | None, Query(max_length=255)]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model_exclude_unset=True,
)
async def create(
    payload: CreateItemRequest,
    caller: Caller,
    conn: Db,
    cipher: Crypto,
) -> CreatedItem:
    item = await create_item(
        conn,
        cipher,
        user_id=caller,
        name=payload.name,
        username=payload.username,
        url=payload.url,
        password=payload.password,
        notes=payload.notes,
    )

    # Leaving `password` unset — rather than setting it to None — is what keeps
    # the field out of the response when the caller sent their own.
    if item.generated_password is None:
        return CreatedItem(
            id=item.id,
            name=item.name,
            username=item.username,
            url=item.url,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

    return CreatedItem(
        id=item.id,
        name=item.name,
        username=item.username,
        url=item.url,
        password=item.generated_password,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.get("")
async def index(
    caller: Caller,
    conn: Db,
    page: Page = 1,
    per_page: PerPage = DEFAULT_PAGE_SIZE,
    q: Search = None,
) -> ItemPage:
    found = await list_items(conn, user_id=caller, page=page, per_page=per_page, search=q)

    data = [
        ItemSummary(
            id=row["id"],
            name=row["name"],
            username=row["username"],
            url=row["url"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in found.rows
    ]

    meta = PageMeta(
        page=page,
        per_page=per_page,
        total=found.total,
        pages=math.ceil(found.total / per_page),
    )

    return ItemPage(data=data, meta=meta)


@router.post("/{item_id}/reveal")
async def reveal(
    item_id: UUID,
    payload: RevealRequest,
    caller: Caller,
    conn: Db,
    cipher: Crypto,
) -> RevealedSecrets:
    secrets = await reveal_item(
        conn,
        cipher,
        user_id=caller,
        item_id=item_id,
        account_password=payload.password,
    )

    return RevealedSecrets(
        password=secrets.password,
        notes=secrets.notes,
    )


@router.patch("/{item_id}", response_model_exclude_unset=True)
async def update(
    item_id: UUID,
    payload: UpdateItemRequest,
    caller: Caller,
    conn: Db,
    cipher: Crypto,
) -> CreatedItem:
    # Only the fields actually present in the body count as changes; a field left
    # out and a field sent as null have to mean different things.
    changes = payload.model_dump(include=payload.model_fields_set, exclude={"generate_password"})

    item = await update_item(
        conn,
        cipher,
        user_id=caller,
        item_id=item_id,
        changes=changes,
        generate_password=payload.generate_password,
    )

    if item.generated_password is None:
        return CreatedItem(
            id=item.id,
            name=item.name,
            username=item.username,
            url=item.url,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

    return CreatedItem(
        id=item.id,
        name=item.name,
        username=item.username,
        url=item.url,
        password=item.generated_password,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def destroy(item_id: UUID, caller: Caller, conn: Db) -> Response:
    await delete_item(conn, user_id=caller, item_id=item_id)

    return Response(status_code=status.HTTP_204_NO_CONTENT)
