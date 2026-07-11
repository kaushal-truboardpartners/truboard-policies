"""Document versioning: soft-delete old version + increment + re-key blob.

Per CLAUDE.md:
- Soft-delete: set is_deleted=True + deleted_at on the old Policy and ALL its chunks.
- Version increment: new Policy row gets version = old_version + 1.
- Blob key scheme: ``policies/v{version}/{new_id}.pdf``.
- Existing chunks are never mutated — new chunk rows will be inserted by M4's
  ingestion job after versioning.

This module operates only on Policy / PolicyChunk rows; the caller (routes.py)
handles blob upload and ingestion job enqueue.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Policy, PolicyChunk

logger = logging.getLogger(__name__)


async def soft_delete_policy(
    policy: Policy,
    session: AsyncSession,
) -> None:
    """Mark ``policy`` and all its active chunks as deleted.

    This does NOT delete blob storage content — the blob_key remains valid for
    any in-flight SAS URLs and for audit purposes.
    """
    now = datetime.now(UTC)

    # Soft-delete the policy row.
    policy.is_deleted = True
    policy.deleted_at = now

    # Soft-delete all non-deleted chunks belonging to this policy.
    await session.execute(
        update(PolicyChunk)
        .where(
            PolicyChunk.document_id == policy.id,
            PolicyChunk.is_deleted.is_(False),
        )
        .values(is_deleted=True, deleted_at=now)
    )

    await session.flush()  # propagate before the caller commits
    logger.info("Soft-deleted policy %s (v%d) and its chunks", policy.id, policy.version)


async def create_replacement_policy(
    old_policy: Policy,
    new_id: uuid.UUID,
    blob_url: str,
    blob_key: str,
    file_hash: str,
    uploaded_by: uuid.UUID,
    session: AsyncSession,
) -> Policy:
    """Insert a new Policy row as a replacement for ``old_policy``.

    Returns the (unflushed) new Policy row; the caller commits after enqueuing
    the ingestion job so the row and the job land in the same transaction.
    """
    new_version = old_policy.version + 1
    new_policy = Policy(
        id=new_id,
        policy_name=old_policy.policy_name,
        version=new_version,
        file_hash=file_hash,
        blob_url=blob_url,
        blob_key=blob_key,
        is_deleted=False,
        uploaded_by=uploaded_by,
    )
    session.add(new_policy)
    logger.info(
        "Created replacement policy %s v%d (replaces %s v%d)",
        new_id,
        new_version,
        old_policy.id,
        old_policy.version,
    )
    return new_policy
