"""initial schema: users, policies, policy_chunks, ingestion_jobs + pgvector + HNSW

Revision ID: 0001
Revises:
Create Date: 2026-06-25

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 1536


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("microsoft_oid", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("microsoft_oid", name="uq_users_microsoft_oid"),
    )

    op.create_table(
        "policies",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("policy_name", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("file_hash", sa.Text(), nullable=False),
        sa.Column("blob_url", sa.Text(), nullable=False),
        sa.Column("blob_key", sa.Text(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("uploaded_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    op.create_table(
        "policy_chunks",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("document_id", sa.UUID(), sa.ForeignKey("policies.id"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("chunk_type", sa.Text(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("section_heading", sa.Text(), nullable=True),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_policy_chunks_document_id", "policy_chunks", ["document_id"])

    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("document_id", sa.UUID(), sa.ForeignKey("policies.id"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("chunks_created", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_ingestion_jobs_document_id", "ingestion_jobs", ["document_id"])

    # HNSW partial index for cosine similarity over active chunks only.
    # Plain CREATE INDEX (not CONCURRENTLY) is correct here: the table is empty at creation,
    # so there's no lock-contention reason for CONCURRENTLY. (See CLAUDE.md / reindex_all.py.)
    op.create_index(
        "policy_chunks_embedding_idx",
        "policy_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_where=sa.text("is_deleted = false"),
    )


def downgrade() -> None:
    op.drop_index("policy_chunks_embedding_idx", table_name="policy_chunks")
    op.drop_index("ix_ingestion_jobs_document_id", table_name="ingestion_jobs")
    op.drop_table("ingestion_jobs")
    op.drop_index("ix_policy_chunks_document_id", table_name="policy_chunks")
    op.drop_table("policy_chunks")
    op.drop_table("policies")
    op.drop_table("users")
    op.execute("DROP EXTENSION IF EXISTS vector")
