"""The password must reach the clipboard on stdin, and never through argv."""

from __future__ import annotations

import os
import stat

import pytest
from napm import clipboard
from napm.screens.modals import copy_password

PASSWORD = "K7#mQ2vX!pL9"


@pytest.fixture
def fake_tool(tmp_path, monkeypatch):
    """A stand-in clipboard tool that writes whatever it is fed to a file."""
    landed = tmp_path / "landed.txt"
    script = tmp_path / "pretend-copy"

    script.write_text(f'#!/bin/sh\ncat > "{landed}"\n')
    script.chmod(script.stat().st_mode | stat.S_IEXEC)

    monkeypatch.setenv("PATH", str(tmp_path), prepend=os.pathsep)
    monkeypatch.setattr(clipboard, "TOOLS", [("pretend-copy", [])])

    return landed


def test_no_tool_installed_is_not_a_crash(monkeypatch):
    monkeypatch.setattr(clipboard, "TOOLS", [("a-tool-nobody-has", [])])

    assert clipboard.find_tool() is None


def test_the_first_tool_on_the_path_wins(monkeypatch, tmp_path):
    monkeypatch.setattr(clipboard, "TOOLS", [("a-tool-nobody-has", []), ("sh", ["-c", "cat"])])

    found = clipboard.find_tool()

    assert found is not None
    assert found[0] == "sh"


async def test_the_password_travels_on_stdin(fake_tool):
    tool = await clipboard.to_system_clipboard(PASSWORD)

    assert tool == "pretend-copy"
    assert fake_tool.read_text() == PASSWORD


async def test_nothing_installed_reports_nothing_copied(monkeypatch):
    monkeypatch.setattr(clipboard, "TOOLS", [("a-tool-nobody-has", [])])

    assert await clipboard.to_system_clipboard(PASSWORD) is None


async def test_a_tool_that_fails_reports_nothing_copied(monkeypatch):
    monkeypatch.setattr(clipboard, "TOOLS", [("false", [])])

    assert await clipboard.to_system_clipboard(PASSWORD) is None


class FakeApp:
    def __init__(self):
        self.copied = None

    def copy_to_clipboard(self, text):
        self.copied = text


class FakeWidget:
    def __init__(self):
        self.app = FakeApp()
        self.notices = []

    def notify(self, message, severity="information"):
        self.notices.append((message, severity))


async def test_the_escape_sequence_goes_out_either_way(monkeypatch):
    """Over ssh it is the only route that can reach the real terminal."""
    monkeypatch.setattr(clipboard, "TOOLS", [("a-tool-nobody-has", [])])

    widget = FakeWidget()

    await copy_password(widget, PASSWORD)

    assert widget.app.copied == PASSWORD


async def test_nothing_copied_is_not_reported_as_copied(monkeypatch):
    monkeypatch.setattr(clipboard, "TOOLS", [("a-tool-nobody-has", [])])

    widget = FakeWidget()

    await copy_password(widget, PASSWORD)

    message, severity = widget.notices[0]

    assert severity == "warning"
    assert "install" in message


async def test_a_real_copy_says_which_tool_took_it(fake_tool):
    widget = FakeWidget()

    await copy_password(widget, PASSWORD)

    message, severity = widget.notices[0]

    assert severity == "information"
    assert "pretend-copy" in message
    assert fake_tool.read_text() == PASSWORD
