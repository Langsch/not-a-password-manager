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

Ten endpoints under `/api/v1`, one error envelope, and a full path with `curl` —
**[api.md](api.md)**.

---

# Running it

Everything runs in Docker. You need Docker with Compose, and nothing else.

### 1. Configure

```bash
cp .env.example .env
```

Then generate the encryption key and put it in `.env`:

```bash
docker run --rm python:3.13-alpine python -c \
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
