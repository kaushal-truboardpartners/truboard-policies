"""Two-phase vector retrieval with cosine deduplication.

Per FRD §5.3 / CLAUDE.md:

Phase 1 — Scoped:
  Search policy_chunks WHERE document_id = active_document_id AND is_deleted = false.
  Top-K = RETRIEVAL_SCOPED_TOP_K (default 3).
  If max(similarity) >= confidence_threshold: use Phase 1 results.

Phase 2 — Global fallback:
  Search all policy_chunks WHERE is_deleted = false.
  Top-K = RETRIEVAL_GLOBAL_TOP_K (default 5).
  If top result.document_id != active_document_id: set redirect metadata.

Deduplication: after merging, drop any chunk whose embedding has cosine
similarity > DEDUP_COSINE_THRESHOLD (0.97) to an already-accepted chunk.

CLAUDE.md invariants upheld:
- is_deleted = false on every query — no exceptions.
- Cosine similarity computed in SQL via pgvector <=> operator (1 - distance).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    """One retrieved chunk with its metadata and similarity score."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    policy_name: str
    chunk_text: str
    chunk_type: str
    page_number: int
    section_heading: str | None
    similarity: float
    embedding: list[float]


@dataclass
class RetrievalResult:
    """Output of the two-phase retrieval."""

    chunks: list[RetrievedChunk]
    used_phase: int  # 1 or 2
    redirect_document_id: uuid.UUID | None
    redirect_page: int | None


# ---------------------------------------------------------------------------
# SQL helpers
# ---------------------------------------------------------------------------

_SCOPED_SQL = text(
    """
    SELECT
        pc.id               AS chunk_id,
        pc.document_id,
        p.policy_name,
        pc.chunk_text,
        pc.chunk_type,
        pc.page_number,
        pc.section_heading,
        1 - (pc.embedding <=> CAST(:qvec AS vector)) AS similarity,
        pc.embedding::text AS embedding_text
    FROM policy_chunks pc
    JOIN policies p ON p.id = pc.document_id
    WHERE pc.document_id = :doc_id
      AND pc.is_deleted = false
    ORDER BY pc.embedding <=> CAST(:qvec AS vector)
    LIMIT :top_k
    """
)

_GLOBAL_SQL = text(
    """
    SELECT
        pc.id               AS chunk_id,
        pc.document_id,
        p.policy_name,
        pc.chunk_text,
        pc.chunk_type,
        pc.page_number,
        pc.section_heading,
        1 - (pc.embedding <=> CAST(:qvec AS vector)) AS similarity,
        pc.embedding::text AS embedding_text
    FROM policy_chunks pc
    JOIN policies p ON p.id = pc.document_id
    WHERE pc.is_deleted = false
    ORDER BY pc.embedding <=> CAST(:qvec AS vector)
    LIMIT :top_k
    """
)


def _vec_to_pg(embedding: list[float]) -> str:
    """Format a float list as a PostgreSQL vector literal string."""
    return "[" + ",".join(f"{v:.8f}" for v in embedding) + "]"


def _parse_embedding(text_val: str) -> list[float]:
    """Parse a pgvector text representation back to a Python list."""
    return [float(x) for x in text_val.strip("[]").split(",")]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = sum(x * x for x in a) ** 0.5
    mag_b = sum(x * x for x in b) ** 0.5
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def _deduplicate(
    chunks: list[RetrievedChunk], threshold: float
) -> list[RetrievedChunk]:
    """Remove chunks whose embedding is nearly identical to an already-accepted one."""
    accepted: list[RetrievedChunk] = []
    for chunk in chunks:
        duplicate = any(
            _cosine_similarity(chunk.embedding, kept.embedding) > threshold
            for kept in accepted
        )
        if not duplicate:
            accepted.append(chunk)
    return accepted


def _row_to_chunk(row) -> RetrievedChunk:  # type: ignore[no-untyped-def]
    return RetrievedChunk(
        chunk_id=row.chunk_id,
        document_id=row.document_id,
        policy_name=row.policy_name,
        chunk_text=row.chunk_text,
        chunk_type=row.chunk_type,
        page_number=row.page_number,
        section_heading=row.section_heading,
        similarity=float(row.similarity),
        embedding=_parse_embedding(row.embedding_text),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def retrieve(
    query_embedding: list[float],
    active_document_id: uuid.UUID,
    db: AsyncSession,
    *,
    confidence_threshold: float = 0.75,
    scoped_top_k: int = 3,
    global_top_k: int = 5,
    dedup_threshold: float = 0.97,
) -> RetrievalResult:
    """Run two-phase retrieval and return deduplicated chunks + redirect metadata."""
    qvec = _vec_to_pg(query_embedding)

    # ---- Phase 1: scoped to active document ---------------------------------
    scoped_rows = (
        await db.execute(
            _SCOPED_SQL,
            {"qvec": qvec, "doc_id": str(active_document_id), "top_k": scoped_top_k},
        )
    ).fetchall()

    scoped_chunks = [_row_to_chunk(r) for r in scoped_rows]
    max_score = max((c.similarity for c in scoped_chunks), default=0.0)

    if max_score >= confidence_threshold:
        logger.debug(
            "Phase 1 hit: max_score=%.3f >= threshold=%.2f", max_score, confidence_threshold
        )
        deduped = _deduplicate(scoped_chunks, dedup_threshold)
        return RetrievalResult(
            chunks=deduped,
            used_phase=1,
            redirect_document_id=None,
            redirect_page=None,
        )

    # ---- Phase 2: global fallback -------------------------------------------
    logger.debug(
        "Phase 1 miss: max_score=%.3f < threshold=%.2f — running global search",
        max_score,
        confidence_threshold,
    )
    global_rows = (
        await db.execute(
            _GLOBAL_SQL,
            {"qvec": qvec, "top_k": global_top_k},
        )
    ).fetchall()

    global_chunks = [_row_to_chunk(r) for r in global_rows]
    deduped = _deduplicate(global_chunks, dedup_threshold)

    # Determine redirect: top result in a different document → redirect.
    redirect_document_id: uuid.UUID | None = None
    redirect_page: int | None = None
    if deduped and deduped[0].document_id != active_document_id:
        redirect_document_id = deduped[0].document_id
        redirect_page = deduped[0].page_number
        logger.info(
            "Phase 2 redirect → document %s page %d", redirect_document_id, redirect_page
        )

    return RetrievalResult(
        chunks=deduped,
        used_phase=2,
        redirect_document_id=redirect_document_id,
        redirect_page=redirect_page,
    )
