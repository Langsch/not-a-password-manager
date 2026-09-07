from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest
from fastapi.testclient import TestClient


def _with_database(url: str, name: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(parts._replace(path=f"/{name}"))


@pytest.fixture(scope="session")
def base_url() -> str:
    return os.environ["DATABASE_URL"]


@pytest.fixture
def scratch_db(base_url: str) -> Iterator[object]:
    """Hands out empty throwaway databases, dropped afterwards."""
    created: list[str] = []

    def make(name: str) -> str:
        with psycopg.connect(_with_database(base_url, "postgres"), autocommit=True) as conn:
            conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
            conn.execute(f'CREATE DATABASE "{name}"')
        created.append(name)
        return _with_database(base_url, name)

    yield make

    with psycopg.connect(_with_database(base_url, "postgres"), autocommit=True) as conn:
        for name in created:
            conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


TEST_DATABASE = "passwords_test"
TABLES = ("sessions", "items", "users")


@pytest.fixture(scope="session")
def migrated_database(base_url: str) -> Iterator[str]:
    """A database with the migrations applied, shared by the whole run."""
    admin = _with_database(base_url, "postgres")
    dsn = _with_database(base_url, TEST_DATABASE)

    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{TEST_DATABASE}" WITH (FORCE)')
        conn.execute(f'CREATE DATABASE "{TEST_DATABASE}"')

    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=Path(__file__).resolve().parents[1],
        env={"PATH": "/opt/venv/bin:/usr/bin:/bin", "DATABASE_URL": dsn},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    yield dsn

    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{TEST_DATABASE}" WITH (FORCE)')


@pytest.fixture
def client(migrated_database: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """The real application, pointed at an empty migrated database."""
    from app.config import get_settings
    from app.main import app

    with psycopg.connect(migrated_database, autocommit=True) as conn:
        conn.execute(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE")

    monkeypatch.setenv("DATABASE_URL", migrated_database)
    get_settings.cache_clear()
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client
    finally:
        get_settings.cache_clear()


@pytest.fixture
def sql(migrated_database: str) -> Iterator[object]:
    """Run a query against the test database and get rows back."""

    def run(query: str, params: tuple[object, ...] = ()) -> list[tuple[object, ...]]:
        with psycopg.connect(migrated_database) as conn, conn.cursor() as cur:
            cur.execute(query, params)  # type: ignore[arg-type]
            return cur.fetchall()

    yield run
