"""Admin API — M3: upload. M4: ingestion jobs, policy list, replace.

All endpoints require admin role (DB-verified via require_admin — CLAUDE.md).
"""

from __future__ import annotations

import hashlib
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from admin.ingestion.job import get_queue, register_job, release_queue, run_ingestion_job
from admin.schemas import (
    JobEnqueuedResponse,
    PolicyListItem,
    ReplaceResultItem,
    UploadResultItem,
)
from admin.upload import process_upload
from admin.versioning import create_replacement_policy, soft_delete_policy
from auth.middleware import require_admin
from config import Settings, get_settings
from db.connection import get_db
from db.models import IngestionJob, Policy, User
from storage.blob import BlobStorageService, BlobUploadError, get_blob_service

router = APIRouter(prefix="/api/admin", tags=["admin"])

_PDF_MAGIC = b"%PDF"
_INITIAL_VERSION = 1


# ---- POST /api/admin/upload -------------------------------------------------
# M3 endpoint (kept): upload + dedup + blob store. Does NOT enqueue ingestion.
# M4 adds /enqueue so upload and ingest can be called separately (or together
# via the replace flow). The existing test suite covers this endpoint.


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


# ---- POST /api/admin/upload-and-ingest --------------------------------------
# M4: upload + immediately enqueue an ingestion job. Returns job_id for SSE polling.


@router.post("/upload-and-ingest", response_model=JobEnqueuedResponse)
async def upload_and_ingest(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    blob_service: BlobStorageService = Depends(get_blob_service),
    settings: Settings = Depends(get_settings),
) -> JobEnqueuedResponse:
    """Upload a single PDF and immediately enqueue an ingestion job.

    Returns ``job_id`` which the client uses to stream progress via
    ``GET /api/admin/jobs/{job_id}/stream``.
    """
    # Re-use the existing upload pipeline.
    try:
        policy = await process_upload(file, user, db, blob_service, settings)
    except HTTPException:
        raise

    # Create the IngestionJob row in queued state.
    job_id = uuid.uuid4()
    job = IngestionJob(
        id=job_id,
        document_id=policy.id,
        status="queued",
        progress=0,
    )
    db.add(job)
    await db.commit()

    # Register the SSE queue *before* the background task starts so the /stream
    # endpoint never races with the task's first emit.
    register_job(job_id)

    background_tasks.add_task(run_ingestion_job, job_id, policy.id)

    return JobEnqueuedResponse(job_id=job_id, document_id=policy.id)


# ---- GET /api/admin/jobs/{job_id}/stream ------------------------------------


@router.get("/jobs/{job_id}/stream")
async def stream_job_progress(
    job_id: uuid.UUID,
    _user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """SSE stream of ingestion job progress events.

    Events are JSON objects:
        { "job_id": "...", "status": "parsing|chunking|...", "progress": 0-100, "message": "..." }

    The stream closes when a 'complete' or 'failed' event is emitted.
    """
    # Verify the job exists.
    job = await db.get(IngestionJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    import asyncio
    import json

    q = get_queue(job_id)

    async def _generate():
        # If the job already finished before the client connected, stream a
        # synthetic terminal event from the DB record and close.
        if q is None:
            payload = json.dumps(
                {
                    "job_id": str(job_id),
                    "status": job.status,
                    "progress": job.progress,
                    "message": job.error_message or "",
                    **({"chunks_created": job.chunks_created} if job.chunks_created else {}),
                }
            )
            yield f"data: {payload}\n\n"
            return

        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue

                yield f"data: {json.dumps(event)}\n\n"

                if event.get("status") in ("complete", "failed"):
                    break
        finally:
            release_queue(job_id)

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---- GET /api/admin/policies ------------------------------------------------


@router.get("/policies", response_model=list[PolicyListItem])
async def list_all_policies(
    _user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[PolicyListItem]:
    """List ALL policies (including soft-deleted), alphabetical. Admin-only."""
    result = await db.execute(
        select(Policy).order_by(Policy.policy_name, Policy.version.desc())
    )
    return [
        PolicyListItem(
            id=p.id,
            policy_name=p.policy_name,
            version=p.version,
            is_deleted=p.is_deleted,
        )
        for p in result.scalars().all()
    ]


# ---- POST /api/admin/policies/{id}/replace ----------------------------------


@router.post("/policies/{policy_id}/replace", response_model=ReplaceResultItem)
async def replace_policy(
    policy_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    blob_service: BlobStorageService = Depends(get_blob_service),
    settings: Settings = Depends(get_settings),
) -> ReplaceResultItem:
    """Replace an existing policy with a new PDF version.

    1. Validates the incoming file (PDF magic, size, hash dedup).
    2. Soft-deletes the old Policy + all its chunks.
    3. Uploads the new PDF to blob (key: ``policies/v{n+1}/{new_id}.pdf``).
    4. Creates a new Policy row with version+1.
    5. Enqueues an ingestion job for the new policy.

    Returns the new policy id + job id for SSE progress tracking.
    """
    # 1. Load and validate the old policy.
    old_policy = await db.get(Policy, policy_id)
    if old_policy is None or old_policy.is_deleted:
        raise HTTPException(status_code=404, detail="Policy not found or already deleted")

    # 2. Read and validate the new file.
    content = await file.read()
    is_pdf = content.startswith(_PDF_MAGIC) or file.content_type == "application/pdf"
    if not is_pdf:
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {settings.max_upload_size_mb} MB limit",
        )

    file_hash = hashlib.sha256(content).hexdigest()
    # Dedup against ALL policies including soft-deleted (same rule as initial upload).
    existing = (
        await db.execute(select(Policy).where(Policy.file_hash == file_hash))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=409, detail="This document has already been uploaded"
        )

    # 3. Upload new blob.
    new_id = uuid.uuid4()
    new_version = old_policy.version + 1
    blob_key = f"policies/v{new_version}/{new_id}.pdf"
    try:
        blob_url = await blob_service.upload_pdf(content, blob_key)
    except BlobUploadError as exc:
        raise HTTPException(
            status_code=502,
            detail="Something went wrong while uploading the document. Please try again.",
        ) from exc

    # 4. Soft-delete old + create new in one transaction.
    await soft_delete_policy(old_policy, db)
    new_policy = await create_replacement_policy(
        old_policy=old_policy,
        new_id=new_id,
        blob_url=blob_url,
        blob_key=blob_key,
        file_hash=file_hash,
        uploaded_by=user.id,
        session=db,
    )

    # 5. Create ingestion job row.
    job_id = uuid.uuid4()
    job = IngestionJob(
        id=job_id,
        document_id=new_id,
        status="queued",
        progress=0,
    )
    db.add(job)
    await db.commit()

    register_job(job_id)
    background_tasks.add_task(run_ingestion_job, job_id, new_id)

    return ReplaceResultItem(
        old_id=policy_id,
        new_id=new_id,
        policy_name=new_policy.policy_name,
        version=new_version,
        job_id=job_id,
    )
