# not-a-password-manager

A self-hosted password notebook. Run it on your own machine or your home server,
sign in with an email and a password, and keep your passwords somewhere that
belongs to you.

Most password managers ask you to trust a company with your secrets, or hand you a
zero-knowledge design whose price is that forgetting one password destroys
everything you stored. This one takes a third road, and it only works because of
who runs it: you are the operator, so the server is allowed to hold the key,
it just never keeps that key next to the data.

## How secrets are stored

Each item's password and notes are encrypted with **AES-256-GCM** before they reach
the database. The key comes from an environment variable and is never written to
the database. Service name, username and URL stay in the clear, which is what makes
search and sorting a plain SQL clause.

|  | |
| --- | --- |
| **Protects against** | a leaked backup, a stolen disk, a database dump in the wrong hands |
| **Does not protect against** | a server compromised while running — whoever executes code on it reads everything |

**Losing the encryption key means losing every password.** Back it up separately
from the database.

## Signing in, and revealing

A session lasts **7 days of inactivity** and **30 days** total, whichever comes
first. Every request pushes the first deadline forward. Signing out ends it
immediately, and changing your password drops every device.

Being signed in shows you your items. **Seeing a stored password requires typing
your account password again**, every time — which is what makes a long session safe
to leave open.

## Stack

FastAPI · PostgreSQL 18+ · psycopg 3 with raw SQL · Alembic · Docker

---

# The API

Base: `/api/v1` · Auth: `Authorization: Bearer <token>`

Dates are ISO-8601 with an offset. Every id in a URL or a response is a UUID — the
database's sequential id never leaves.

### Errors

Every failure uses the same envelope:

```json
{ "error": { "code": "ITEM_NOT_FOUND", "message": "No such item." } }
```

`code` is the contract and its text never changes. `message` is for humans and
**must not be interpreted by code**.

| code | HTTP | When |
| --- | --- | --- |
| `VALIDATION_ERROR` | 422 | missing body, missing field, or malformed input |
| `UNAUTHENTICATED` | 401 | token absent, unknown, or expired |
| `INVALID_CREDENTIALS` | 401 | wrong email or password |
| `EMAIL_ALREADY_REGISTERED` | 409 | that email already has an account |
| `ITEM_NOT_FOUND` | 404 | the item does not exist **or is not yours** |
| `INTERNAL_ERROR` | 500 | unexpected failure, with no internal detail |

Someone else's item returns `404`, not `403` — a `403` would confirm that it exists.

---

## Account

### `POST /auth/register`

```json
{ "email": "rafael@example.com", "password": "the account password" }
```
```json
// 201
{ "id": "018f3a2b-…", "email": "rafael@example.com",
  "created_at": "2026-09-07T14:22:10-03:00" }
```
`VALIDATION_ERROR` · `EMAIL_ALREADY_REGISTERED`

Returns no token — only login issues tokens.

---

### `POST /auth/login`

```json
{ "email": "rafael@example.com", "password": "the account password" }
```
```json
// 200
{ "token": "9f2a7c1e4b8d…", "expires_at": "2026-09-14T14:22:10-03:00" }
```
`VALIDATION_ERROR` · `INVALID_CREDENTIALS`

The token is opaque: 32 random bytes with nothing readable inside. Store the string
and repeat it on later requests. There is no `/auth/refresh` — every authenticated
request renews the deadline.

---

### `POST /auth/logout`

No body. `204`. The token stops working on the next request.

`UNAUTHENTICATED`

---

### `PUT /account/password`

```json
{ "current_password": "…", "new_password": "…" }
```
`204` · `VALIDATION_ERROR` · `INVALID_CREDENTIALS` · `UNAUTHENTICATED`

Requires the current password even with a valid token.

**Deletes every session, including yours** — you sign in again afterwards.

---

## Items

### `GET /items`

```
GET /items?page=1&per_page=50&q=git
```

| Parameter | Default | Range |
| --- | --- | --- |
| `page` | 1 | >= 1 |
| `per_page` | 50 | 1 to 200 |
| `q` | — | searches `name` and `username` |

```json
// 200
{
  "data": [
    { "id": "019a7f31-…", "name": "GitHub", "username": "rafael",
      "url": "https://github.com",
      "created_at": "2026-09-07T14:22:10-03:00",
      "updated_at": "2026-09-07T14:22:10-03:00" }
  ],
  "meta": { "page": 1, "per_page": 50, "total": 137, "pages": 3 }
}
```
`VALIDATION_ERROR` · `UNAUTHENTICATED`

**Passwords and notes never appear here.** Ordering is fixed: `name`, then id.
A page past the end returns `200` with an empty `data`.

---

### `POST /items`

```json
{ "name": "GitHub", "username": "rafael", "url": "https://github.com",
  "password": "K7#mQ2vX!pL9", "notes": null }
```

**`password` is optional.** Leave it out and the server generates one and returns it
in the response.

```json
// 201 — the password field appears only when it was generated
{ "id": "019a7f31-…", "name": "GitHub", "username": "rafael", "url": null,
  "password": "hQ7-vk2Rm9-Ldn4Tzb",
  "created_at": "2026-09-07T14:22:10-03:00",
  "updated_at": "2026-09-07T14:22:10-03:00" }
```

Required: `name`. · `VALIDATION_ERROR` · `UNAUTHENTICATED`

---

### `POST /items/{id}/reveal`

Reveals the secret fields. **Requires the account password** on top of the token.

```json
{ "password": "the account password" }
```
```json
// 200
{ "password": "K7#mQ2vX!pL9", "notes": "recovery key is in the physical safe" }
```
`VALIDATION_ERROR` · `INVALID_CREDENTIALS` · `ITEM_NOT_FOUND` · `UNAUTHENTICATED`

This is the only place an **already stored** password leaves the server. The
account password is checked before the item is looked up, so a `404` never tells a
caller holding only a token which ids exist.

---

### `PATCH /items/{id}`

Only the fields you send change.

```json
{ "password": "the new password" }
```
```json
{ "generate_password": true }
```

Returns the whole item. The `password` field appears in the response only when it
was generated.

`VALIDATION_ERROR` (empty body, unknown field, or `password` and
`generate_password` together) · `ITEM_NOT_FOUND` · `UNAUTHENTICATED`

Does not require the account password.

---

### `DELETE /items/{id}`

`204`, no body. The row is gone for real; there is no trash.

`ITEM_NOT_FOUND` · `UNAUTHENTICATED`

---

## Operations

### `GET /health`

`200` if the service is up and can reach the database. No authentication.

---

# Running it

Everything runs in Docker. You need Docker with Compose, and nothing else.

### 1. Configure

```bash
cp .env.example .env
```

Then generate the encryption key and put it in `.env`:

```bash
docker run --rm python:3.12-alpine python -c \
  "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

```bash
# .env
POSTGRES_PASSWORD=change-me
ENCRYPTION_KEY=<the value you just generated>
```

**Keep that key somewhere safe, outside the database backup.** Without it, what is
in the database does not come back. The service refuses to start without it.

### 2. Start

```bash
docker compose up -d db                        # database
docker compose run --rm api alembic upgrade head   # schema
docker compose up -d api                       # service
```

Migrations are a separate command from boot, on purpose — two instances starting
together must not race each other through the same revisions.

The API is on `http://localhost:8000`. Check it:

```bash
curl http://localhost:8000/api/v1/health
```

### Everyday commands

```bash
docker compose logs -f api          # follow logs
docker compose run --rm api pytest  # tests
docker compose down                 # stop
docker compose down -v              # stop and wipe the database
```

`docker compose down -v` deletes the volume. Everything you stored goes with it.

### Upgrading

```bash
git pull
docker compose build api
docker compose run --rm api alembic upgrade head
docker compose up -d api
```

### Backups

Two things, and keeping them together defeats the point:

```bash
docker compose exec db pg_dump -U postgres passwords > backup.sql
```

...and the `ENCRYPTION_KEY` from your `.env`, stored somewhere else entirely.

---

# Using it

A full path with `curl`:

```bash
BASE=http://localhost:8000/api/v1

# 1. create the account
curl -X POST $BASE/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"rafael@example.com","password":"a good password"}'

# 2. sign in
TOKEN=$(curl -s -X POST $BASE/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"rafael@example.com","password":"a good password"}' \
  | jq -r .token)

# 3. store a password, letting the server generate it
curl -X POST $BASE/items \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"GitHub","username":"rafael","url":"https://github.com"}'

# 4. list them (no passwords)
curl $BASE/items -H "Authorization: Bearer $TOKEN"

# 5. reveal — requires the account password
curl -X POST $BASE/items/019a7f31-…/reveal \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"password":"a good password"}'

# 6. rotate
curl -X PATCH $BASE/items/019a7f31-… \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"generate_password":true}'

# 7. sign out
curl -X POST $BASE/auth/logout -H "Authorization: Bearer $TOKEN"
```

### Checking that encryption is working

Store a password you recognise, then look for it in a dump:

```bash
docker compose exec db pg_dump -U postgres passwords | grep "the-password-you-stored"
```

No output is the expected result.

---

## What this project does not do

| | Comes in when |
| --- | --- |
| 2FA | there is a user other than you |
| Password reset by email | an email provider is configured |
| Sharing an item | there is someone to share with |
| Item version history | you overwrite something by accident |
| Attachments | there is an item that does not fit in text |
| Folders and tags | the list grows enough to be annoying |
| Importing from another manager | you actually migrate |
| Weak-password auditing | the basics are standing |
