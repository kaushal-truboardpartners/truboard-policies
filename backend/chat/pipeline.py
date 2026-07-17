"""RAG pipeline orchestrator.

Per CLAUDE.md / FRD §5:
1. Rate-limit check (429 + Retry-After on breach).
2. Sanitise input.
3. Hinglish detect → rewrite to English if needed.
4. Embed the (rewritten) query.
5. Two-phase retrieval (scoped → global).
6. Build prompt with token-budget enforcement.
7. LLM call: temperature=0, max 800 tokens, 15s timeout, 1 retry at 2s.
8. Parse structured JSON from response tail; graceful fallback on parse error.
9. Record query in rate-log; append turns to session history.
10. Return ChatResponse.

CLAUDE.md invariants:
- temperature=0 always.
- tiktoken for all token counting.
- is_deleted=false enforced inside retrieval.py.
- User input wrapped in <user_query>…</user_query> inside context.py.
- System prompt read from file inside context.py.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from dataclasses import dataclass, field

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from chat.context import build_messages
from chat.retrieval import RetrievalResult, retrieve
from chat.rewriter import is_hinglish, rewrite_to_english
from chat.session import (
    append_turn,
    check_rate_limit,
    get_history,
    record_query,
)
from config import get_settings
from llm.client import LLMClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


@dataclass
class Citation:
    policy: str
    page: int
    section: str


@dataclass
class ChatResponse:
    answer: str
    citations: list[Citation] = field(default_factory=list)
    redirect_document_id: uuid.UUID | None = None
    redirect_page: int | None = None
    confidence: str = "found"  # "found" | "not_found" | "out_of_scope"


# ---------------------------------------------------------------------------
# JSON parsing from LLM tail
# ---------------------------------------------------------------------------

# The system prompt asks the LLM to append a JSON block after the answer.
# We parse the LAST JSON object in the response (robust to inline code fences).
_JSON_BLOCK_RE = re.compile(r"\{[^{}]*\}", re.DOTALL)


def _extract_json(text: str) -> tuple[str, dict]:
    """Split ``text`` into (answer_part, parsed_json).

    Finds the last {...} block that contains a 'confidence' key, scanning
    backwards to support nested curly braces.
    Falls back to empty dict on any parse failure (FRD FR-RAG-017).
    """
    text_stripped = text.strip()
    end_idx = text_stripped.rfind("}")
    if end_idx == -1:
        logger.warning("Failed to find any '}' in LLM response")
        return text.strip(), {}

    # Scan backwards for candidate opening braces.
    idx = text_stripped.rfind("{", 0, end_idx)
    while idx != -1:
        candidate = text_stripped[idx : end_idx + 1]
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict) and "confidence" in parsed:
                answer = text_stripped[:idx].strip()
                # Clean up markdown code block markers if the LLM wrapped the JSON.
                if answer.endswith("```json"):
                    answer = answer[:-7].strip()
                elif answer.endswith("```"):
                    answer = answer[:-3].strip()
                return answer, parsed
        except json.JSONDecodeError:
            pass
        idx = text_stripped.rfind("{", 0, idx)

    logger.warning("Failed to parse structured JSON containing 'confidence' from LLM response")
    return text.strip(), {}


def _parse_response(raw: str, retrieval: RetrievalResult) -> ChatResponse:
    """Build a ChatResponse from the raw LLM output string."""
    answer, meta = _extract_json(raw)

    citations: list[Citation] = []
    for c in meta.get("citations", []):
        try:
            citations.append(
                Citation(
                    policy=str(c.get("policy", "")),
                    page=int(c.get("page", 0)),
                    section=str(c.get("section", "")),
                )
            )
        except (TypeError, ValueError):
            pass

    # Redirect: prefer what the LLM said, fall back to retrieval metadata.
    raw_redirect_id = meta.get("redirect_document_id")
    redirect_document_id: uuid.UUID | None = None
    if raw_redirect_id and raw_redirect_id != "null":
        try:
            redirect_document_id = uuid.UUID(str(raw_redirect_id))
        except ValueError:
            redirect_document_id = retrieval.redirect_document_id
    else:
        redirect_document_id = retrieval.redirect_document_id

    raw_redirect_page = meta.get("redirect_page")
    redirect_page: int | None = None
    if raw_redirect_page is not None and raw_redirect_page != "null":
        try:
            redirect_page = int(raw_redirect_page)
        except (TypeError, ValueError):
            redirect_page = retrieval.redirect_page
    else:
        redirect_page = retrieval.redirect_page

    confidence = meta.get("confidence", "found")
    if confidence not in ("found", "not_found", "out_of_scope"):
        confidence = "found"

    return ChatResponse(
        answer=answer,
        citations=citations,
        redirect_document_id=redirect_document_id,
        redirect_page=redirect_page,
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# LLM call with timeout + retry
# ---------------------------------------------------------------------------


async def _call_llm(
    messages: list[dict[str, str]],
    llm: LLMClient,
    *,
    timeout: float,
    max_tokens: int,
) -> str:
    """Call the LLM. One retry at 2s backoff on timeout. 503 on second failure."""
    for attempt in range(2):
        try:
            response = await asyncio.wait_for(
                llm.client.chat.completions.create(
                    model=llm.chat_model,
                    temperature=0,
                    max_tokens=max_tokens,
                    messages=messages,
                ),
                timeout=timeout,
            )
            return (response.choices[0].message.content or "").strip()
        except asyncio.TimeoutError:
            if attempt == 0:
                logger.warning("LLM timeout on attempt 1; retrying after 2s")
                await asyncio.sleep(2)
            else:
                logger.error("LLM timeout on attempt 2; returning 503")
                raise HTTPException(
                    status_code=503,
                    detail="Temporarily unavailable. Please try again in a moment.",
                )
    return ""  # unreachable


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def run_pipeline(
    query: str,
    active_document_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
    llm: LLMClient,
) -> ChatResponse:
    """Full RAG pipeline. Raises HTTPException on rate-limit / timeout / 503."""
    settings = get_settings()

    # 1. Rate limit.
    allowed, retry_after = check_rate_limit(user_id)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Query limit reached. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    # 2. Sanitise + Hinglish.
    effective_query = query  # original preserved for history
    if is_hinglish(query):
        logger.info("Hinglish detected — rewriting")
        effective_query = await rewrite_to_english(query, llm)

    # 3. Embed query.
    emb_response = await llm.client.embeddings.create(
        model=llm.embedding_model,
        input=[effective_query],
    )
    query_embedding: list[float] = emb_response.data[0].embedding

    # 4. Retrieve.
    retrieval = await retrieve(
        query_embedding=query_embedding,
        active_document_id=active_document_id,
        db=db,
        confidence_threshold=settings.retrieval_confidence_threshold,
        scoped_top_k=settings.retrieval_scoped_top_k,
        global_top_k=settings.retrieval_global_top_k,
        dedup_threshold=settings.dedup_cosine_threshold,
    )

    # 5. Build prompt.
    history = get_history(user_id)
    messages = build_messages(
        query=effective_query,
        chunks=retrieval.chunks,
        history=history,
        token_budget=settings.context_token_budget,
    )

    # 6. LLM call.
    raw = await _call_llm(
        messages,
        llm,
        timeout=float(settings.llm_timeout_seconds),
        max_tokens=settings.llm_max_output_tokens,
    )

    # 7. Parse response.
    chat_response = _parse_response(raw, retrieval)

    # 8. Record in rate-log and session.
    record_query(user_id)
    append_turn(user_id, "user", query)  # store original, not rewritten
    append_turn(user_id, "assistant", chat_response.answer)

    return chat_response
