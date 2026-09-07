"""What you chose inside the app, remembered for the next time.

Distinct from `napm.config` on purpose: that one is the environment, settled
before the app starts and not changeable from inside. This one is the opposite
— things you pick while using it, which would be lost otherwise.

Nothing secret goes here, which is why it is a plain file rather than the
guarded one `napm.session` writes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from napm import session


def path() -> Path:
    """Resolved on each call so it follows `session.CONFIG_DIR`, which is the
    one place the directory is decided."""
    return session.CONFIG_DIR / "preferences.json"


@dataclass(frozen=True)
class Preferences:
    theme: str = ""


def load() -> Preferences:
    """What was stored, or the empty defaults.

    A missing or damaged file means the same thing as never having chosen
    anything, and the defaults are the answer either way.
    """
    try:
        raw = path().read_text(encoding="utf-8")
    except OSError:
        return Preferences()

    try:
        body = json.loads(raw)
    except json.JSONDecodeError:
        return Preferences()

    if not isinstance(body, dict):
        return Preferences()

    return _from_body(body)


def save(preferences: Preferences) -> None:
    session.CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    body = {"theme": preferences.theme}

    text = json.dumps(body, indent=2) + "\n"

    path().write_text(text, encoding="utf-8")


def _from_body(body: dict[str, Any]) -> Preferences:
    theme = body.get("theme")

    if not isinstance(theme, str):
        return Preferences()

    return Preferences(theme=theme)
