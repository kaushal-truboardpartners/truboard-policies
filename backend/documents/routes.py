"""Documents API — list active policies and mint fresh SAS URLs for the viewer.

Both endpoints require an authenticated user (any employee, not just admins).
Every query filters `is_deleted = false` (CLAUDE.md).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.middleware import get_current_user
from db.connection import get_db
from db.models import Policy, User
from documents.schemas import DocumentListItem, DocumentUrlResponse
from storage.blob import BlobStorageService, get_blob_service

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("", response_model=list[DocumentListItem])
async def list_documents(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentListItem]:
    """Active policies, alphabetical by name."""
    result = await db.execute(
        select(Policy).where(Policy.is_deleted.is_(False)).order_by(Policy.policy_name)
    )
    return [
        DocumentListItem(id=p.id, policy_name=p.policy_name, version=p.version)
        for p in result.scalars().all()
    ]


@router.get("/{document_id}/url", response_model=DocumentUrlResponse)
async def get_document_url(
    document_id: uuid.UUID,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    blob_service: BlobStorageService = Depends(get_blob_service),
) -> DocumentUrlResponse:
    """Fresh 1h read-only SAS URL for the document. 404 if missing or deleted."""
    result = await db.execute(
        select(Policy).where(Policy.id == document_id, Policy.is_deleted.is_(False))
    )
    policy = result.scalar_one_or_none()
    if policy is None:
        raise HTTPException(status_code=404, detail="Document not found")

    url, expires_at = blob_service.generate_sas_url(policy.blob_key)
    return DocumentUrlResponse(url=url, expires_at=expires_at)
