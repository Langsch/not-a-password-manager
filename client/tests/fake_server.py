"""A stand-in for the API, good enough to hold the client to its contract.

It answers the ten routes with the shapes `README.md` documents, including the
error envelope. It is not a second implementation of the product: there is no
encryption and no hashing here, only the responses the client has to read.
"""

from __future__ import annotations

import json
import secrets
import string
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx

ALPHABET = string.ascii_letters + string.digits + "!#$%&*+-=?@^_~"


def _now():
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _envelope(status, code, message):
    body = {"error": {"code": code, "message": message}}

    return httpx.Response(status, json=body)


class FakeServer:
    def __init__(self):
        self.users = {}
        self.tokens = {}
        self.items = {}
        self.reveal_calls = 0

    # --- transport ----------------------------------------------------------

    def transport(self):
        return httpx.MockTransport(self.handle)

    def handle(self, request):
        path = request.url.path.removeprefix("/api/v1")
        method = request.method

        if path == "/health":
            return httpx.Response(200, json={"status": "ok"})

        if path == "/auth/register" and method == "POST":
            return self.register(self.body(request))

        if path == "/auth/login" and method == "POST":
            return self.login(self.body(request))

        if path == "/auth/logout" and method == "POST":
            return self.logout(request)

        if path == "/items" and method == "GET":
            return self.list_items(request)

        if path == "/items" and method == "POST":
            return self.create_item(request)

        if path.endswith("/reveal") and method == "POST":
            item_id = path.removeprefix("/items/").removesuffix("/reveal")
            return self.reveal(request, item_id)

        if path.startswith("/items/") and method == "PATCH":
            return self.update_item(request, path.removeprefix("/items/"))

        if path.startswith("/items/") and method == "DELETE":
            return self.delete_item(request, path.removeprefix("/items/"))

        return _envelope(404, "NOT_FOUND", "No such path.")

    # --- helpers ------------------------------------------------------------

    def body(self, request):
        if not request.content:
            return None

        try:
            return json.loads(request.content)
        except json.JSONDecodeError:
            return None

    def caller(self, request):
        header = request.headers.get("Authorization", "")

        if not header.startswith("Bearer "):
            return None

        return self.tokens.get(header.removeprefix("Bearer "))

    def summary(self, item):
        return {
            "id": item["id"],
            "name": item["name"],
            "username": item["username"],
            "url": item["url"],
            "created_at": item["created_at"],
            "updated_at": item["updated_at"],
        }

    # --- routes -------------------------------------------------------------

    def register(self, body):
        if body is None or "email" not in body or "password" not in body:
            return _envelope(422, "VALIDATION_ERROR", "Missing field.")

        if body["email"] in self.users:
            return _envelope(409, "EMAIL_ALREADY_REGISTERED", "That email already has an account.")

        self.users[body["email"]] = body["password"]

        return httpx.Response(
            201,
            json={"id": str(uuid4()), "email": body["email"], "created_at": _now()},
        )

    def login(self, body):
        if body is None or "email" not in body or "password" not in body:
            return _envelope(422, "VALIDATION_ERROR", "Missing field.")

        stored = self.users.get(body["email"])

        if stored is None or stored != body["password"]:
            return _envelope(401, "INVALID_CREDENTIALS", "Wrong email or password.")

        token = secrets.token_hex(32)
        self.tokens[token] = body["email"]

        expires_at = datetime.now(UTC) + timedelta(days=7)

        return httpx.Response(
            200,
            json={"token": token, "expires_at": expires_at.isoformat().replace("+00:00", "Z")},
        )

    def logout(self, request):
        email = self.caller(request)

        if email is None:
            return _envelope(401, "UNAUTHENTICATED", "Missing, unknown or expired token.")

        header = request.headers["Authorization"].removeprefix("Bearer ")
        self.tokens.pop(header, None)

        return httpx.Response(204)

    def list_items(self, request):
        email = self.caller(request)

        if email is None:
            return _envelope(401, "UNAUTHENTICATED", "Missing, unknown or expired token.")

        query = request.url.params.get("q", "")
        page = int(request.url.params.get("page", 1))
        per_page = int(request.url.params.get("per_page", 50))

        mine = [item for item in self.items.values() if item["owner"] == email]

        if query:
            needle = query.lower()
            mine = [
                item
                for item in mine
                if needle in item["name"].lower() or needle in (item["username"] or "").lower()
            ]

        mine.sort(key=lambda item: (item["name"], item["id"]))

        total = len(mine)
        pages = max((total + per_page - 1) // per_page, 1)
        start = (page - 1) * per_page

        data = [self.summary(item) for item in mine[start : start + per_page]]
        meta = {"page": page, "per_page": per_page, "total": total, "pages": pages}

        return httpx.Response(200, json={"data": data, "meta": meta})

    def create_item(self, request):
        email = self.caller(request)

        if email is None:
            return _envelope(401, "UNAUTHENTICATED", "Missing, unknown or expired token.")

        body = self.body(request)

        if body is None or not body.get("name"):
            return _envelope(422, "VALIDATION_ERROR", "Missing field.")

        generated = None

        if "password" not in body:
            generated = "".join(secrets.choice(ALPHABET) for _ in range(20))

        moment = _now()

        item = {
            "id": str(uuid4()),
            "owner": email,
            "name": body["name"],
            "username": body.get("username"),
            "url": body.get("url"),
            "password": generated if generated is not None else body["password"],
            "notes": body.get("notes"),
            "created_at": moment,
            "updated_at": moment,
        }

        self.items[item["id"]] = item

        answer = self.summary(item)
        answer["password"] = generated

        return httpx.Response(201, json=answer)

    def reveal(self, request, item_id):
        email = self.caller(request)

        if email is None:
            return _envelope(401, "UNAUTHENTICATED", "Missing, unknown or expired token.")

        body = self.body(request)

        if body is None or "password" not in body:
            return _envelope(422, "VALIDATION_ERROR", "Missing field.")

        self.reveal_calls += 1

        # The account password is checked before the item is looked up, so a
        # 404 never tells a caller holding only a token which ids exist.
        if self.users.get(email) != body["password"]:
            return _envelope(401, "INVALID_CREDENTIALS", "Wrong email or password.")

        item = self.items.get(item_id)

        if item is None or item["owner"] != email:
            return _envelope(404, "ITEM_NOT_FOUND", "No such item.")

        return httpx.Response(200, json={"password": item["password"], "notes": item["notes"]})

    def update_item(self, request, item_id):
        email = self.caller(request)

        if email is None:
            return _envelope(401, "UNAUTHENTICATED", "Missing, unknown or expired token.")

        body = self.body(request)

        if not body:
            return _envelope(422, "VALIDATION_ERROR", "The body must say something.")

        known = {"name", "username", "url", "password", "notes", "generate_password"}

        if set(body) - known:
            return _envelope(422, "VALIDATION_ERROR", "Unknown field.")

        if "password" in body and body.get("generate_password"):
            return _envelope(422, "VALIDATION_ERROR", "Send one or the other.")

        item = self.items.get(item_id)

        if item is None or item["owner"] != email:
            return _envelope(404, "ITEM_NOT_FOUND", "No such item.")

        generated = None

        if body.pop("generate_password", False):
            generated = "".join(secrets.choice(ALPHABET) for _ in range(20))
            item["password"] = generated

        for name, value in body.items():
            item[name] = value

        item["updated_at"] = _now()

        answer = self.summary(item)
        answer["password"] = generated

        return httpx.Response(200, json=answer)

    def delete_item(self, request, item_id):
        email = self.caller(request)

        if email is None:
            return _envelope(401, "UNAUTHENTICATED", "Missing, unknown or expired token.")

        item = self.items.get(item_id)

        if item is None or item["owner"] != email:
            return _envelope(404, "ITEM_NOT_FOUND", "No such item.")

        del self.items[item_id]

        return httpx.Response(204)
