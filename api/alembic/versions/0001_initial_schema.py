"""Initial schema: users, sessions, items

Revision ID: 0001
Revises:
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
TS = sa.TIMESTAMP(timezone=True)

# Flush left and byte-identical to schema.sql: PostgreSQL stores a function body
# verbatim, so indenting this would show up as a difference in the drift test.
SET_UPDATED_AT = """\
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql
"""


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", TS, nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", TS, nullable=False, server_default=sa.text("now()")),
    ]


def _touch_trigger(table: str) -> None:
    op.execute(
        f"""
        CREATE TRIGGER {table}_set_updated_at
            BEFORE UPDATE ON {table} FOR EACH ROW
            WHEN (OLD.* IS DISTINCT FROM NEW.*)
            EXECUTE FUNCTION set_updated_at()
        """
    )


def upgrade() -> None:
    op.execute(SET_UPDATED_AT)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "external_id", UUID, nullable=False, unique=True, server_default=sa.text("uuidv7()")
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        *_timestamps(),
    )
    op.execute("""
        CREATE UNIQUE INDEX users_email_lower_key
            ON users (lower(email))
    """)
    _touch_trigger("users")

    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("token_hash", sa.LargeBinary, nullable=False, unique=True),
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("expires_at", TS, nullable=False),
        sa.Column("absolute_expires_at", TS, nullable=False),
        sa.Column("created_at", TS, nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "absolute_expires_at >= expires_at", name="sessions_absolute_after_sliding"
        ),
    )
    op.create_index("sessions_user_id_idx", "sessions", ["user_id"])

    op.create_table(
        "items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "external_id", UUID, nullable=False, unique=True, server_default=sa.text("uuidv7()")
        ),
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("username", sa.String(255)),
        sa.Column("url", sa.Text),
        sa.Column("password_encrypted", sa.Text, nullable=False),
        sa.Column("notes_encrypted", sa.Text),
        *_timestamps(),
        sa.CheckConstraint("password_encrypted LIKE 'v1.%'", name="items_password_looks_encrypted"),
        sa.CheckConstraint(
            "notes_encrypted IS NULL OR notes_encrypted LIKE 'v1.%'",
            name="items_notes_look_encrypted",
        ),
    )
    op.create_index("items_user_id_name_id_idx", "items", ["user_id", "name", "id"])
    _touch_trigger("items")


def downgrade() -> None:
    op.drop_table("items")
    op.drop_table("sessions")
    op.drop_table("users")
    op.execute("""
        DROP FUNCTION IF EXISTS set_updated_at()
    """)
