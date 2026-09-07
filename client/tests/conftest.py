from __future__ import annotations

import httpx
import pytest
from napm import api, session
from tests.fake_server import FakeServer

EMAIL = "rafael@example.com"
PASSWORD = "the account password"


@pytest.fixture
def server(monkeypatch):
    """A fake API, wired in where the real transport would be built."""
    fake = FakeServer()
    fake.users[EMAIL] = PASSWORD

    def build_http(root: str) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=root, transport=fake.transport())

    monkeypatch.setattr(api, "build_http", build_http)

    return fake


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    """Keep the session file out of the real ~/.config while testing."""
    directory = tmp_path / "config"

    monkeypatch.setattr(session, "CONFIG_DIR", directory)
    monkeypatch.setattr(session, "SESSION_FILE", directory / "session.json")

    return directory
