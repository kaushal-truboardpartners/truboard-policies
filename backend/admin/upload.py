"""Upload pipeline: validate a PDF, dedup by hash, store in blob, create Policy row.

M3 scope: storage + Policy record only. Ingestion (extract/chunk/embed) is M4.
"""

import hashlib
import uuid
from pathlib import PurePosixPath

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import Settings
from db.models import Policy, User
from storage.blob import BlobStorageService, BlobUploadError

_PDF_MAGIC = b"%PDF"
_INITIAL_VERSION = 1


def _resolve_policy_name(filename: str | None) -> str:
    """Derive the policy name from the uploaded filename's stem, else 'untitled'."""
    if filename:
        stem = PurePosixPath(filename).stem
        if stem:
            return stem
    return "untitled"


async def process_upload(
    file: UploadFile,
    user: User,
    db: AsyncSession,
    blob_service: BlobStorageService,
    settings: Settings,
) -> Policy:
    """Validate, dedup, upload to blob, and persist a new Policy. Returns the row."""
    content = await file.read()

    # 1. Must be a PDF — trust the magic bytes, fall back to the declared type.
    is_pdf = content.startswith(_PDF_MAGIC) or file.content_type == "application/pdf"
    if not is_pdf:
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # 2. Size limit.
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {settings.max_upload_size_mb} MB limit",
        )

    # 3. Dedup by content hash — including soft-deleted policies (no is_deleted filter).
    file_hash = hashlib.sha256(content).hexdigest()
    existing = (
        await db.execute(select(Policy).where(Policy.file_hash == file_hash))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="This document has already been uploaded")

    # 4. Store in blob: key embeds version + UUID (matches M4 versioning scheme).
    document_id = uuid.uuid4()
    version = _INITIAL_VERSION
    blob_key = f"policies/v{version}/{document_id}.pdf"
    try:
        blob_url = await blob_service.upload_pdf(content, blob_key)
    except BlobUploadError as exc:
        raise HTTPException(
            status_code=502,
            detail="Something went wrong while uploading the document. Please try again.",
        ) from exc

    # 5. Persist the Policy row.
    policy = Policy(
        id=document_id,
        policy_name=_resolve_policy_name(file.filename),
        version=version,
        file_hash=file_hash,
        blob_url=blob_url,
        blob_key=blob_key,
        uploaded_by=user.id,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return policy
