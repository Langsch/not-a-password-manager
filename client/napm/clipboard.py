"""Getting a password into the system clipboard.

Textual's own `copy_to_clipboard` writes the OSC 52 escape sequence and nothing
else. That is the right thing over ssh — the sequence travels to whatever
terminal you are actually sitting at — but plenty of terminals refuse it, and
they refuse it silently. So we try a local tool first and tell the truth about
what happened.

The text goes in on **stdin**, never as an argument: a command line is readable
by anyone who can run `ps`, and this one carries a password.
"""

from __future__ import annotations

import asyncio
import shutil

# In order of preference: the Wayland tool, then the two X11 ones, then macOS.
TOOLS: list[tuple[str, list[str]]] = [
    ("wl-copy", []),
    ("xclip", ["-selection", "clipboard"]),
    ("xsel", ["--clipboard", "--input"]),
    ("pbcopy", []),
]

# wl-copy and xclip fork to keep serving the selection, so this is a guard
# against a hang, not a real expectation.
TIMEOUT = 2.0


def find_tool() -> tuple[str, list[str]] | None:
    for name, arguments in TOOLS:
        if shutil.which(name) is not None:
            return name, arguments

    return None


async def to_system_clipboard(text: str) -> str | None:
    """The name of the tool that took the text, or None if none did."""
    found = find_tool()

    if found is None:
        return None

    name, arguments = found

    try:
        process = await asyncio.create_subprocess_exec(
            name,
            *arguments,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )

        await asyncio.wait_for(process.communicate(text.encode()), TIMEOUT)
    except (OSError, TimeoutError):
        return None

    if process.returncode != 0:
        return None

    return name
