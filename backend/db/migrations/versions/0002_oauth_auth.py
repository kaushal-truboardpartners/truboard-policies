"""Replace microsoft_oid with slug on users; add oauth_tokens table.

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-26

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- users: microsoft_oid → slug ---
    op.add_column("users", sa.Column("slug", sa.Text(), nullable=True))
    # Backfill slug from microsoft_oid for existing rows
    op.execute("UPDATE users SET slug = microsoft_oid WHERE slug IS NULL")
    op.alter_column("users", "slug", nullable=False)
    op.create_unique_constraint("uq_users_slug", "users", ["slug"])
    op.drop_constraint("uq_users_microsoft_oid", "users", type_="unique")
    op.drop_column("users", "microsoft_oid")

    # --- oauth_tokens ---
    op.create_table(
        "oauth_tokens",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("exp", sa.Integer(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_oauth_tokens_token", "oauth_tokens", ["token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_oauth_tokens_token", table_name="oauth_tokens")
    op.drop_table("oauth_tokens")

    op.add_column("users", sa.Column("microsoft_oid", sa.Text(), nullable=True))
    op.execute("UPDATE users SET microsoft_oid = slug WHERE microsoft_oid IS NULL")
    op.alter_column("users", "microsoft_oid", nullable=False)
    op.create_unique_constraint("uq_users_microsoft_oid", "users", ["microsoft_oid"])
    op.drop_constraint("uq_users_slug", "users", type_="unique")
    op.drop_column("users", "slug")
