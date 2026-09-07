"""Request and response shapes for the item endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_PAGE_SIZE = 200
DEFAULT_PAGE_SIZE = 50


class CreateItemRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    username: str | None = Field(default=None, max_length=255)
    url: str | None = None
    password: str | None = Field(default=None, max_length=1024)
    notes: str | None = None


class UpdateItemRequest(BaseModel):
    """Only the fields present in the body change.

    `extra="forbid"` turns a misspelled field into a 422 rather than a silent
    no-op, which is the failure that would be found weeks later.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    username: str | None = Field(default=None, max_length=255)
    url: str | None = None
    password: str | None = Field(default=None, max_length=1024)
    notes: str | None = None
    generate_password: bool = False

    @model_validator(mode="after")
    def check_the_body_says_something(self) -> UpdateItemRequest:
        if not self.model_fields_set:
            raise ValueError("the body must carry at least one field")

        if "password" in self.model_fields_set and self.generate_password:
            raise ValueError("send either password or generate_password, not both")

        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name cannot be cleared")

        return self


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
