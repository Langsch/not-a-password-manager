"""Request and response shapes for the item endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

MAX_PAGE_SIZE = 200
DEFAULT_PAGE_SIZE = 50


class CreateItemRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    username: str | None = Field(default=None, max_length=255)
    url: str | None = None
    password: str | None = Field(default=None, max_length=1024)
    notes: str | None = None


class ItemSummary(BaseModel):
    """What a listing carries. No secret fields, ever."""

    id: UUID
    name: str
    username: str | None
    url: str | None
    created_at: datetime
    updated_at: datetime


class CreatedItem(ItemSummary):
    """`password` appears only when the server drew it."""

    password: str | None = None


class RevealRequest(BaseModel):
    password: str


class RevealedSecrets(BaseModel):
    password: str
    notes: str | None


class PageMeta(BaseModel):
    page: int
    per_page: int
    total: int
    pages: int


class ItemPage(BaseModel):
    data: list[ItemSummary]
    meta: PageMeta
