"""schema.sql and the migrations describe the same database.

Two descriptions of one thing drift. This applies schema.sql to one database
and the migrations to another, then compares what PostgreSQL actually built:
columns, constraints, indexes, triggers and functions.

Any difference fails the test.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import psycopg
from psycopg.rows import tuple_row

SCHEMA_SQL = Path(__file__).resolve().parents[1] / "schema.sql"
PROJECT = Path(__file__).resolve().parents[1]


def describe(dsn: str) -> list[tuple[str, str, str]]:
    with psycopg.connect(dsn) as conn, conn.cursor(row_factory=tuple_row) as cur:
        return cur.execute(
            """
        SELECT 'column'     AS kind,
               table_name || '.' || column_name AS name,
               data_type
                 || coalesce('(' || character_maximum_length || ')', '')
                 || ' null=' || is_nullable
                 || ' default=' || coalesce(column_default, '-') AS definition
          FROM information_schema.columns
         WHERE table_schema = 'public' AND table_name <> 'alembic_version'
        UNION ALL
        SELECT 'constraint',
               conrelid::regclass::text || '.' || conname,
               pg_get_constraintdef(oid)
          FROM pg_constraint
         WHERE connamespace = 'public'::regnamespace
           AND conrelid::regclass::text <> 'alembic_version'
        UNION ALL
        SELECT 'index', indexname, indexdef
          FROM pg_indexes
         WHERE schemaname = 'public' AND tablename <> 'alembic_version'
        UNION ALL
        SELECT 'trigger', tgname, pg_get_triggerdef(oid)
          FROM pg_trigger
         WHERE NOT tgisinternal
        UNION ALL
        SELECT 'function', proname, pg_get_functiondef(oid)
          FROM pg_proc
         WHERE pronamespace = 'public'::regnamespace
         ORDER BY 1, 2, 3
            """
        ).fetchall()


def test_schema_sql_matches_the_migrations(scratch_db) -> None:  # type: ignore[no-untyped-def]
    target = scratch_db("drift_target")
    migrated = scratch_db("drift_migrated")

    with psycopg.connect(target, autocommit=True) as conn:
        conn.execute(SCHEMA_SQL.read_text())

    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=PROJECT,
        env={"PATH": "/opt/venv/bin:/usr/bin:/bin", "DATABASE_URL": migrated},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    expected = describe(target)
    actual = describe(migrated)

    missing = [row for row in expected if row not in actual]
    extra = [row for row in actual if row not in expected]
    assert not missing and not extra, (
        "schema.sql and the migrations disagree.\n"
        + "".join(f"  only in schema.sql: {r}\n" for r in missing)
        + "".join(f"  only in migrations: {r}\n" for r in extra)
    )


def test_migrations_go_up_and_down(scratch_db) -> None:  # type: ignore[no-untyped-def]
    dsn = scratch_db("migration_cycle")
    env = {"PATH": "/opt/venv/bin:/usr/bin:/bin", "DATABASE_URL": dsn}

    def alembic(*args: str) -> None:
        result = subprocess.run(
            ["alembic", *args], cwd=PROJECT, env=env, capture_output=True, text=True
        )
        assert result.returncode == 0, result.stderr

    def tables() -> set[str]:
        with psycopg.connect(dsn) as conn, conn.cursor(row_factory=tuple_row) as cur:
            rows = cur.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
            ).fetchall()
        return {r[0] for r in rows} - {"alembic_version"}

    alembic("upgrade", "head")
    assert tables() == {"users", "sessions", "items"}

    alembic("downgrade", "base")
    assert tables() == set()
