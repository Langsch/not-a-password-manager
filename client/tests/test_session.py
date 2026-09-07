from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from napm import session

TOKEN = "9f2a7c1e4b8d"


def a_session(days: int = 7) -> session.StoredSession:
    return session.StoredSession(
        base_url="http://localhost:8000",
        token=TOKEN,
        expires_at=datetime.now(UTC) + timedelta(days=days),
        email="rafael@example.com",
    )


def test_a_saved_session_comes_back(config_dir):
    saved = a_session()

    session.save(saved)

    assert session.load() == saved


def test_the_file_is_readable_only_by_its_owner(config_dir):
    session.save(a_session())

    mode = session.SESSION_FILE.stat().st_mode & 0o777

    assert mode == 0o600


def test_rewriting_an_existing_file_keeps_the_mode(config_dir):
    session.save(a_session())
    session.SESSION_FILE.chmod(0o644)

    session.save(a_session())

    assert session.SESSION_FILE.stat().st_mode & 0o777 == 0o600


def test_the_account_password_is_never_in_the_file(config_dir):
    session.save(a_session())

    body = json.loads(session.SESSION_FILE.read_text())

    assert set(body) == {"base_url", "token", "expires_at", "email"}


def test_nothing_stored_is_not_an_error(config_dir):
    assert session.load() is None


def test_a_damaged_file_reads_as_nothing_stored(config_dir):
    config_dir.mkdir(parents=True)
    session.SESSION_FILE.write_text("{ this is not json")

    assert session.load() is None


def test_a_file_missing_a_field_reads_as_nothing_stored(config_dir):
    config_dir.mkdir(parents=True)
    session.SESSION_FILE.write_text(json.dumps({"token": TOKEN}))

    assert session.load() is None


def test_a_file_from_before_the_email_was_stored_still_loads(config_dir):
    saved = a_session()
    session.save(saved)

    body = json.loads(session.SESSION_FILE.read_text())
    del body["email"]
    session.SESSION_FILE.write_text(json.dumps(body))

    loaded = session.load()

    assert loaded is not None
    assert loaded.token == TOKEN
    assert loaded.email == ""


def test_an_expired_session_says_so():
    assert a_session(days=-1).is_expired()
    assert not a_session(days=1).is_expired()


def test_clearing_removes_the_file(config_dir):
    session.save(a_session())

    session.clear()

    assert not session.SESSION_FILE.exists()
    session.clear()
