from __future__ import annotations

import os
from collections.abc import Iterator
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest


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
