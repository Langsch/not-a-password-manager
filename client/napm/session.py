"""The session token on disk, and nothing else.

The token is what survives closing the app; the account password never reaches
this file, or any other. It is held in memory while the app is open and gone
when it closes, which is why reopening asks for it again before the first
reveal.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_BASE_URL = "http://localhost:8000"

CONFIG_DIR = Path.home() / ".config" / "not-a-password-manager"
SESSION_FILE = CONFIG_DIR / "session.json"


@dataclass(frozen=True)
class StoredSession:
    base_url: str
    token: str
    expires_at: datetime

    def is_expired(self) -> bool:
        return self.expires_at <= datetime.now(UTC)


def load() -> StoredSession | None:
    """The stored session, or ``None`` when there is nothing usable.

    A missing, unreadable or malformed file is not an error worth stopping for
    — it means the same thing as never having signed in, and the login screen
    is the answer either way.
    """
    try:
        raw = SESSION_FILE.read_text(encoding="utf-8")
    except OSError:
        return None

    try:
        body = json.loads(raw)
    except json.JSONDecodeError:
        return None

    if not isinstance(body, dict):
        return None

    return _from_body(body)


def save(session: StoredSession) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(CONFIG_DIR, 0o700)

    body = {
        "base_url": session.base_url,
        "token": session.token,
        "expires_at": session.expires_at.isoformat(),
    }

    text = json.dumps(body, indent=2) + "\n"

    # Opened with the mode rather than written and then chmod'ed: between the
    # two there is a moment where the token sits in a file anyone can read.
    descriptor = os.open(SESSION_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)

    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(text)

    # An existing file keeps its old mode through O_CREAT, so say it again.
    os.chmod(SESSION_FILE, 0o600)


def clear() -> None:
    SESSION_FILE.unlink(missing_ok=True)


def _from_body(body: dict[str, Any]) -> StoredSession | None:
    base_url = body.get("base_url")
    token = body.get("token")
    expires_at = body.get("expires_at")

    if not isinstance(base_url, str) or not isinstance(token, str):
        return None

    if not isinstance(expires_at, str):
        return None

    try:
        deadline = datetime.fromisoformat(expires_at)
    except ValueError:
        return None

    if deadline.tzinfo is None:
        return None

    return StoredSession(base_url=base_url, token=token, expires_at=deadline)
