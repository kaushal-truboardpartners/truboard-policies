"""Chat API routes.

POST /api/chat/message  — full RAG pipeline (rate-limited, auth required)
DELETE /api/chat/session — clear conversation history for the calling user
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from auth.middleware import get_current_user
from chat.pipeline import ChatResponse, Citation, run_pipeline
from chat.session import clear_session
from db.connection import get_db
from db.models import User
from llm.client import LLMClient, get_llm_client

router = APIRouter(prefix="/api/chat", tags=["chat"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    query: str
    active_document_id: uuid.UUID


class CitationOut(BaseModel):
    policy: str
    page: int
    section: str


class ChatResponseOut(BaseModel):
    answer: str
    citations: list[CitationOut]
    redirect_document_id: uuid.UUID | None
    redirect_page: int | None
    confidence: str  # "found" | "not_found" | "out_of_scope"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/message", response_model=ChatResponseOut)
async def chat_message(
    body: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    llm: LLMClient = Depends(get_llm_client),
) -> ChatResponseOut:
    """Run the full RAG pipeline and return the answer.

    Rate-limited: 30 queries per user per rolling 60-minute window.
    Returns HTTP 429 with Retry-After header on breach.
    """
    result: ChatResponse = await run_pipeline(
        query=body.query,
        active_document_id=body.active_document_id,
        user_id=user.id,
        db=db,
        llm=llm,
    )
    return ChatResponseOut(
        answer=result.answer,
        citations=[
            CitationOut(policy=c.policy, page=c.page, section=c.section)
            for c in result.citations
        ],
        redirect_document_id=result.redirect_document_id,
        redirect_page=result.redirect_page,
        confidence=result.confidence,
    )


@router.delete("/session", status_code=204)
async def delete_session(
    user: User = Depends(get_current_user),
) -> None:
    """Clear the in-memory conversation history for the requesting user.

    Called on logout or browser refresh (FRD FR-UI-013 / FR-AUTH-005).
    """
    clear_session(user.id)
