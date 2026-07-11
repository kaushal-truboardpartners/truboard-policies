"""Ingestion job state machine + SSE event emitter.

Design (per CLAUDE.md / FRD §9):

- A BackgroundTask runs the full pipeline: extract → chunk → embed → persist.
- Job status transitions: queued → parsing → chunking → embedding → indexing → complete
  (or → failed on any unhandled exception).
- The entire pipeline is wrapped in try/except; any exception sets status=failed
  so the SSE stream always terminates cleanly (CLAUDE.md gotcha).
- The background task creates its OWN DB session — never reuses the request
  session, which is closed before the task runs (CLAUDE.md invariant).
- SSE events are written to an asyncio.Queue; the /stream endpoint reads from it.
  Queue is keyed by job_id in the process-wide job registry below.

Progress mapping (0–100):
  0   queued
  5   parsing
  30  chunking
  50  embedding (start)
  90  embedding (done)
  95  indexing (persisting to DB)
 100  complete
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from admin.ingestion.chunker import build_chunks
from admin.ingestion.embedder import embed_texts
from admin.ingestion.extractor import extract_pdf
from db.connection import AsyncSessionLocal
from db.models import IngestionJob, Policy, PolicyChunk
from llm.client import build_llm_client

logger = logging.getLogger(__name__)

# ---- In-process job registry -----------------------------------------------
# job_id → asyncio.Queue of SSE event dicts.
# Entries are created when a job starts and deleted once the stream consumer
# signals it has read the terminal event (complete / failed).

_JOB_QUEUES: dict[uuid.UUID, asyncio.Queue[dict[str, Any]]] = {}


def register_job(job_id: uuid.UUID) -> asyncio.Queue[dict[str, Any]]:
    """Create a queue for ``job_id`` and return it. Called in the request handler."""
    q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    _JOB_QUEUES[job_id] = q
    return q


def get_queue(job_id: uuid.UUID) -> asyncio.Queue[dict[str, Any]] | None:
    return _JOB_QUEUES.get(job_id)


def release_queue(job_id: uuid.UUID) -> None:
    """Remove the queue once the SSE consumer is done."""
    _JOB_QUEUES.pop(job_id, None)


# ---- SSE helpers ------------------------------------------------------------


def _event(
    job_id: uuid.UUID,
    status: str,
    progress: int,
    *,
    message: str = "",
    chunks_created: int | None = None,
) -> dict[str, Any]:
    return {
        "job_id": str(job_id),
        "status": status,
        "progress": progress,
        "message": message,
        **({"chunks_created": chunks_created} if chunks_created is not None else {}),
    }


async def _emit(q: asyncio.Queue[dict[str, Any]], evt: dict[str, Any]) -> None:
    """Put an event on the queue (non-blocking; queue is unbounded)."""
    await q.put(evt)


# ---- DB helpers -------------------------------------------------------------


async def _update_job(
    session,
    job: IngestionJob,
    *,
    status: str,
    progress: int,
    chunks_created: int | None = None,
    error_message: str | None = None,
) -> None:
    job.status = status
    job.progress = progress
    if chunks_created is not None:
        job.chunks_created = chunks_created
    if error_message is not None:
        job.error_message = error_message
    job.updated_at = datetime.now(UTC)
    await session.commit()


# ---- Main pipeline ----------------------------------------------------------


async def run_ingestion_job(job_id: uuid.UUID, document_id: uuid.UUID) -> None:
    """Full ingestion pipeline. Runs inside a FastAPI BackgroundTask.

    Creates its own DB session (CLAUDE.md). Emits SSE events throughout.
    Always terminates — either 'complete' or 'failed' — so the stream consumer
    can close safely.
    """
    q = get_queue(job_id)
    if q is None:
        # Queue gone (race: consumer already left); log and bail.
        logger.error("run_ingestion_job: no queue for job %s", job_id)
        return

    async with AsyncSessionLocal() as session:
        # Fetch the job row (created by the upload route before enqueueing).
        job_row = await session.get(IngestionJob, job_id)
        if job_row is None:
            logger.error("run_ingestion_job: job %s not found in DB", job_id)
            return

        try:
            # ---- 1. Fetch PDF bytes from DB (blob_key stored on Policy) ----
            await _update_job(session, job_row, status="parsing", progress=5)
            await _emit(q, _event(job_id, "parsing", 5, message="Fetching document…"))

            policy = await session.get(Policy, document_id)
            if policy is None or policy.is_deleted:
                raise ValueError(f"Policy {document_id} not found or deleted")

            # We have the raw bytes stored during upload — re-read from blob.
            # To avoid a second Azure call we store nothing in process; instead we
            # pull the bytes from the blob service attached to the app state.
            # BackgroundTasks don't have a Request, so we import the blob helper.
            from config import get_settings
            from storage.blob import BlobStorageService

            settings = get_settings()
            blob_svc = BlobStorageService(settings)
            try:
                container_client = blob_svc._container_client
                blob_client = container_client.get_blob_client(policy.blob_key)
                stream = await blob_client.download_blob()
                pdf_bytes: bytes = await stream.readall()
            finally:
                await blob_svc.close()

            # ---- 2. Extract -----------------------------------------------
            await _emit(q, _event(job_id, "parsing", 10, message="Extracting text and tables…"))
            blocks = extract_pdf(pdf_bytes)
            if not blocks:
                raise ValueError("No extractable content found in PDF")

            # ---- 3. Chunk -------------------------------------------------
            await _update_job(session, job_row, status="chunking", progress=30)
            await _emit(q, _event(job_id, "chunking", 30, message="Chunking…"))
            chunks = build_chunks(blocks)
            if not chunks:
                raise ValueError("Chunker produced no output (PDF may be image-only)")

            # ---- 4. Embed -------------------------------------------------
            await _update_job(session, job_row, status="embedding", progress=50)
            await _emit(
                q,
                _event(job_id, "embedding", 50, message=f"Embedding {len(chunks)} chunks…"),
            )
            llm = build_llm_client(settings)
            try:
                embeddings = await embed_texts([c.text for c in chunks], llm)
            finally:
                await llm.aclose()

            await _update_job(session, job_row, status="embedding", progress=90)
            await _emit(q, _event(job_id, "embedding", 90, message="Embeddings done"))

            # ---- 5. Persist chunks ----------------------------------------
            await _update_job(session, job_row, status="indexing", progress=95)
            await _emit(q, _event(job_id, "indexing", 95, message="Saving to database…"))

            chunk_rows = [
                PolicyChunk(
                    document_id=document_id,
                    chunk_index=c.chunk_index,
                    chunk_text=c.text,
                    chunk_type=c.chunk_type,
                    page_number=c.page_number,
                    section_heading=c.section_heading,
                    embedding=emb,
                    is_deleted=False,
                )
                for c, emb in zip(chunks, embeddings, strict=True)
            ]
            session.add_all(chunk_rows)
            await _update_job(
                session,
                job_row,
                status="complete",
                progress=100,
                chunks_created=len(chunk_rows),
            )

            await _emit(
                q,
                _event(
                    job_id,
                    "complete",
                    100,
                    message=f"Done — {len(chunk_rows)} chunks indexed",
                    chunks_created=len(chunk_rows),
                ),
            )
            logger.info(
                "Ingestion job %s complete: %d chunks for policy %s",
                job_id,
                len(chunk_rows),
                document_id,
            )

        except Exception as exc:  # noqa: BLE001 — catch-all; log full detail
            logger.error("Ingestion job %s failed: %s", job_id, exc, exc_info=True)
            err = str(exc)[:500]
            try:
                await _update_job(
                    session,
                    job_row,
                    status="failed",
                    progress=job_row.progress,
                    error_message=err,
                )
            except Exception:  # noqa: BLE001
                logger.error("Could not update job %s to failed", job_id, exc_info=True)

            await _emit(
                q,
                _event(job_id, "failed", job_row.progress, message=err),
            )
