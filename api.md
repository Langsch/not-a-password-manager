# The API

The contract. The front door is [README.md](README.md).

Base: `/api/v1` · Auth: `Authorization: Bearer <token>`

Dates are ISO-8601 with an offset — UTC, so they end in `Z`. Every id in a URL or a
response is a UUID; the database's sequential id never leaves.

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

Two more come from the framework, before a route is reached. They are here because
the envelope has no exceptions, not because an endpoint raises them:

| code | HTTP | When |
| --- | --- | --- |
| `NOT_FOUND` | 404 | no such path |
| `METHOD_NOT_ALLOWED` | 405 | the path exists, the method does not |

---

## Account

### `POST /auth/register`

```json
{ "email": "rafael@example.com", "password": "the account password" }
```
```json
// 201
{ "id": "018f3a2b-…", "email": "rafael@example.com",
  "created_at": "2026-09-07T05:32:57.594865Z" }
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
{ "token": "9f2a7c1e4b8d…", "expires_at": "2026-09-14T05:32:57.594865Z" }
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
      "created_at": "2026-09-07T05:32:57.594865Z",
      "updated_at": "2026-09-07T05:32:57.594865Z" }
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
in the response — 20 characters drawn from letters, digits and `!#$%&*+-=?@^_~`,
around 125 bits. There are no options: one good default is one less thing to get
wrong.

```json
// 201 — the password field appears only when it was generated
{ "id": "019a7f31-…", "name": "GitHub", "username": "rafael", "url": null,
  "password": "qZJC@@&ZZ+y7sY+I@_nv",
  "created_at": "2026-09-07T05:32:57.594865Z",
  "updated_at": "2026-09-07T05:32:57.594865Z" }
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
