"""Session tokens.

A token is 32 random bytes and nothing else — it carries no claims, no user id,
no expiry. Everything it means lives in a row of the sessions table, which is
what makes signing out a DELETE instead of a waiting game.

Only the SHA-256 of the token is stored. The token itself is handed out once, in
the login response, and never written down: a database dump must not contain
live sessions.

SHA-256 and not Argon2id, deliberately. Argon2id is slow on purpose because a
password is short and guessable; 32 random bytes are on no list worth
precomputing, so the cost would buy nothing and would be paid on every request.
No salt either, for the same reason and because the lookup is *by* the hash.
"""

from __future__ import annotations

import hashlib
import secrets

TOKEN_BYTES = 32


def new_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def token_digest(token: str) -> bytes:
    encoded = token.encode()
    digest = hashlib.sha256(encoded)
    return digest.digest()
