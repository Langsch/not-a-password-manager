"""The ten endpoints, and the only place in this client that speaks HTTP.

Nothing that draws on the screen imports httpx: the screen calls a method here
and gets back a dataclass or an exception from `errors`.

Every response the API sends is JSON under `/api/v1`, and every failure is the
envelope `errors.from_envelope` reads.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

from napm import errors

API_PREFIX = "/api/v1"

# Long enough for Argon2id on a reveal, short enough that a wrong address is
# reported instead of hanging the screen.
TIMEOUT = httpx.Timeout(10.0)


@dataclass(frozen=True)
class Account:
    id: str
    email: str
    created_at: datetime


@dataclass(frozen=True)
class Session:
    token: str
    expires_at: datetime


@dataclass(frozen=True)
class Item:
    id: str
    name: str
    username: str | None
    url: str | None
    created_at: datetime
    updated_at: datetime
    # Set only when the server drew the password in this same response, on a
    # create or a rotation. A listing never carries it.
    password: str | None = None


@dataclass(frozen=True)
class Page:
    items: list[Item]
    page: int
    per_page: int
    total: int
    pages: int


@dataclass(frozen=True)
class Secrets:
    password: str
    notes: str | None


class _Unset:
    """A field the caller did not mention, as opposed to one set to null.

    `PATCH /items/{id}` changes only the fields present in the body, so
    "leave the username alone" and "clear the username" are different requests
    and `None` cannot mean both.
    """

    def __repr__(self) -> str:
        return "UNSET"


UNSET = _Unset()


@dataclass
class ItemChanges:
    name: str | _Unset = UNSET
    username: str | None | _Unset = UNSET
    url: str | None | _Unset = UNSET
    password: str | _Unset = UNSET
    notes: str | None | _Unset = UNSET
    generate_password: bool = False

    def to_body(self) -> dict[str, Any]:
        body: dict[str, Any] = {}

        if not isinstance(self.name, _Unset):
            body["name"] = self.name

        if not isinstance(self.username, _Unset):
            body["username"] = self.username

        if not isinstance(self.url, _Unset):
            body["url"] = self.url

        if not isinstance(self.password, _Unset):
            body["password"] = self.password

        if not isinstance(self.notes, _Unset):
            body["notes"] = self.notes

        if self.generate_password:
            body["generate_password"] = True

        return body


@dataclass
class Client:
    """One HTTP client against one server, carrying at most one token."""

    base_url: str
    token: str | None = None
    _http: httpx.AsyncClient = field(init=False, repr=False)

    def __post_init__(self) -> None:
        root = self.base_url.rstrip("/") + API_PREFIX

        self._http = build_http(root)

    async def close(self) -> None:
        await self._http.aclose()

    async def health(self) -> bool:
        await self._request("GET", "/health", authenticated=False)

        return True

    async def register(self, email: str, password: str) -> Account:
        body = {"email": email, "password": password}

        answer = await self._request("POST", "/auth/register", body=body, authenticated=False)

        return _account(answer)

    async def login(self, email: str, password: str) -> Session:
        body = {"email": email, "password": password}

        answer = await self._request("POST", "/auth/login", body=body, authenticated=False)

        session = _session(answer)
        self.token = session.token

        return session

    async def logout(self) -> None:
        await self._request("POST", "/auth/logout")

        self.token = None

    async def change_password(self, current_password: str, new_password: str) -> None:
        body = {"current_password": current_password, "new_password": new_password}

        await self._request("PUT", "/account/password", body=body)

        # Changing the password drops every session, this one included.
        self.token = None

    async def list_items(self, page: int = 1, per_page: int = 50, query: str = "") -> Page:
        params: dict[str, Any] = {"page": page, "per_page": per_page}

        if query:
            params["q"] = query

        answer = await self._request("GET", "/items", params=params)

        return _page(answer)

    async def create_item(
        self,
        name: str,
        username: str | None = None,
        url: str | None = None,
        password: str | None = None,
        notes: str | None = None,
    ) -> Item:
        body: dict[str, Any] = {"name": name, "username": username, "url": url, "notes": notes}

        # Omitted, not null: leaving the field out is what asks the server to
        # generate one, while `"password": null` is a malformed request.
        if password is not None:
            body["password"] = password

        answer = await self._request("POST", "/items", body=body)

        return _item(answer)

    async def reveal_item(self, item_id: str, account_password: str) -> Secrets:
        body = {"password": account_password}

        answer = await self._request("POST", f"/items/{item_id}/reveal", body=body)

        return _secrets(answer)

    async def update_item(self, item_id: str, changes: ItemChanges) -> Item:
        body = changes.to_body()

        answer = await self._request("PATCH", f"/items/{item_id}", body=body)

        return _item(answer)

    async def delete_item(self, item_id: str) -> None:
        await self._request("DELETE", f"/items/{item_id}")

    async def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        authenticated: bool = True,
    ) -> Any:
        headers = {}

        if authenticated:
            if self.token is None:
                raise errors.Unauthenticated()

            headers["Authorization"] = f"Bearer {self.token}"

        try:
            response = await self._http.request(
                method,
                path,
                json=body,
                params=params,
                headers=headers,
            )
        except httpx.RequestError as exc:
            raise errors.Unreachable(f"Could not reach {self.base_url}: {exc}") from exc

        return _answer(response)


def build_http(root: str) -> httpx.AsyncClient:
    """The one place a transport is constructed, so a test can hand over another."""
    return httpx.AsyncClient(base_url=root, timeout=TIMEOUT)


def _answer(response: httpx.Response) -> Any:
    if response.status_code == 204:
        return None

    try:
        body = response.json()
    except ValueError:
        body = None

    if response.is_success:
        return body

    raise errors.from_envelope(body)


def _account(body: Any) -> Account:
    return Account(
        id=str(body["id"]),
        email=str(body["email"]),
        created_at=_moment(body["created_at"]),
    )


def _session(body: Any) -> Session:
    return Session(token=str(body["token"]), expires_at=_moment(body["expires_at"]))


def _item(body: Any) -> Item:
    return Item(
        id=str(body["id"]),
        name=str(body["name"]),
        username=body.get("username"),
        url=body.get("url"),
        created_at=_moment(body["created_at"]),
        updated_at=_moment(body["updated_at"]),
        password=body.get("password"),
    )


def _page(body: Any) -> Page:
    meta = body["meta"]

    items = [_item(row) for row in body["data"]]

    return Page(
        items=items,
        page=int(meta["page"]),
        per_page=int(meta["per_page"]),
        total=int(meta["total"]),
        pages=int(meta["pages"]),
    )


def _secrets(body: Any) -> Secrets:
    return Secrets(password=str(body["password"]), notes=body.get("notes"))


def _moment(value: Any) -> datetime:
    return datetime.fromisoformat(str(value))
