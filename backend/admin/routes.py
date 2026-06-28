"""Admin API. M3: document upload (admin-only). M4 adds ingestion jobs/versioning."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from admin.schemas import UploadResultItem
from admin.upload import process_upload
from auth.middleware import require_admin
from config import Settings, get_settings
from db.connection import get_db
from db.models import User
from storage.blob import BlobStorageService, get_blob_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/upload", response_model=list[UploadResultItem])
async def upload_documents(
    files: list[UploadFile] = File(...),
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    blob_service: BlobStorageService = Depends(get_blob_service),
    settings: Settings = Depends(get_settings),
) -> list[UploadResultItem]:
    """Upload one or more policy PDFs. Each file is validated, deduped by hash,
    stored in blob, and recorded — independently. Returns a per-file result list;
    a failure on one file does not block the others.

    Processed sequentially: dedup reads the DB and each row commits before the next
    file, so duplicates within the same batch are caught on the second occurrence.
    """
    results: list[UploadResultItem] = []
    for file in files:
        try:
            policy = await process_upload(file, user, db, blob_service, settings)
            results.append(
                UploadResultItem(
                    filename=file.filename,
                    status="uploaded",
                    id=policy.id,
                    policy_name=policy.policy_name,
                    version=policy.version,
                )
            )
        except HTTPException as exc:
            results.append(
                UploadResultItem(filename=file.filename, status="error", error=exc.detail)
            )
    return results
