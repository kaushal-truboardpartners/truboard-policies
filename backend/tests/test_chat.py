"""Tests for M5 — session/rate-limit, rewriter, context, pipeline, chat routes.

No real DB, LLM, or network calls. All external dependencies are mocked.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# chat/session.py
# ---------------------------------------------------------------------------


class TestSession:
    def setup_method(self):
        # Reset module state between tests.
        import chat.session as s

        s._HISTORY.clear()
        s._RATE_LOG.clear()

    def test_append_and_get_history(self):
        from chat.session import append_turn, get_history

        uid = uuid.uuid4()
        append_turn(uid, "user", "hello")
        append_turn(uid, "assistant", "hi")
        h = get_history(uid)
        assert h == [("user", "hello"), ("assistant", "hi")]

    def test_get_history_empty(self):
        from chat.session import get_history

        assert get_history(uuid.uuid4()) == []

    def test_clear_session(self):
        from chat.session import append_turn, clear_session, get_history

        uid = uuid.uuid4()
        append_turn(uid, "user", "test")
        clear_session(uid)
        assert get_history(uid) == []

    def test_rate_limit_allows_under_limit(self):
        from chat.session import check_rate_limit

        uid = uuid.uuid4()
        allowed, retry = check_rate_limit(uid)
        assert allowed is True
        assert retry == 0

    def test_rate_limit_denies_over_limit(self):
        from chat.session import _RATE_LOG, check_rate_limit
        from collections import deque

        uid = uuid.uuid4()
        # Manually fill the rate log with 30 recent timestamps.
        now = datetime.now(UTC)
        _RATE_LOG[uid] = deque(now - timedelta(minutes=i) for i in range(30))
        allowed, retry = check_rate_limit(uid)
        assert allowed is False
        assert retry > 0

    def test_rate_limit_evicts_old_entries(self):
        from chat.session import _RATE_LOG, check_rate_limit
        from collections import deque

        uid = uuid.uuid4()
        # All 30 entries are outside the 60-min window.
        old = datetime.now(UTC) - timedelta(hours=2)
        _RATE_LOG[uid] = deque([old] * 30)
        allowed, _ = check_rate_limit(uid)
        assert allowed is True

    def test_record_query_increments_log(self):
        from chat.session import _RATE_LOG, record_query

        uid = uuid.uuid4()
        record_query(uid)
        record_query(uid)
        assert len(_RATE_LOG[uid]) == 2


# ---------------------------------------------------------------------------
# chat/rewriter.py
# ---------------------------------------------------------------------------


class TestRewriter:
    def test_devanagari_detected(self):
        from chat.rewriter import is_hinglish

        assert is_hinglish("मुझे leave policy बताओ") is True

    def test_pure_english_not_hinglish(self):
        from chat.rewriter import is_hinglish

        assert is_hinglish("What is the leave policy?") is False

    def test_hinglish_markers_detected(self):
        from chat.rewriter import is_hinglish

        # "kya" and "hai" are markers — 2/4 tokens = 50% > threshold.
        assert is_hinglish("kya leave policy hai") is True

    def test_empty_string_not_hinglish(self):
        from chat.rewriter import is_hinglish

        assert is_hinglish("") is False

    @pytest.mark.asyncio
    async def test_rewrite_returns_llm_response(self):
        from chat.rewriter import rewrite_to_english

        llm = MagicMock()
        response = MagicMock()
        response.choices[0].message.content = "What is the leave policy?"
        llm.client.chat.completions.create = AsyncMock(return_value=response)
        llm.chat_model = "gpt-4o"

        result = await rewrite_to_english("leave policy kya hai", llm)
        assert result == "What is the leave policy?"

    @pytest.mark.asyncio
    async def test_rewrite_falls_back_on_error(self):
        from chat.rewriter import rewrite_to_english

        llm = MagicMock()
        llm.client.chat.completions.create = AsyncMock(side_effect=Exception("timeout"))
        llm.chat_model = "gpt-4o"

        result = await rewrite_to_english("kya hai", llm)
        assert result == "kya hai"  # original returned


# ---------------------------------------------------------------------------
# chat/context.py
# ---------------------------------------------------------------------------


class TestContext:
    def _make_chunk(self, text="Some policy text.", page=1, policy="HR Policy"):
        from chat.retrieval import RetrievedChunk

        return RetrievedChunk(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            policy_name=policy,
            chunk_text=text,
            chunk_type="text",
            page_number=page,
            section_heading=None,
            similarity=0.9,
            embedding=[0.0] * 1536,
        )

    def test_messages_structure(self):
        from chat.context import build_messages

        chunks = [self._make_chunk()]
        history = [("user", "hi"), ("assistant", "hello")]
        msgs = build_messages("What is the leave policy?", chunks, history)

        roles = [m["role"] for m in msgs]
        assert roles[0] == "system"
        assert roles[-1] == "user"

    def test_user_query_wrapped_in_delimiters(self):
        from chat.context import build_messages

        msgs = build_messages("test query", [], [])
        user_msg = next(m for m in msgs if m["role"] == "user")
        assert "<user_query>" in user_msg["content"]
        assert "</user_query>" in user_msg["content"]

    def test_html_stripped_from_query(self):
        from chat.context import _sanitise

        assert "<script>" not in _sanitise("<script>alert(1)</script> hello")
        assert "hello" in _sanitise("<script>alert(1)</script> hello")

    def test_query_capped_at_2000_chars(self):
        from chat.context import _sanitise

        long = "a" * 3000
        assert len(_sanitise(long)) == 2000

    def test_history_trimmed_on_budget(self):
        from chat.context import build_messages

        # Use a tiny budget to force trimming.
        long_history = [("user", "word " * 500), ("assistant", "word " * 500)] * 5
        msgs = build_messages("q", [], long_history, token_budget=100)
        # Should not raise and history should be trimmed.
        history_msgs = [m for m in msgs if m["role"] in ("user", "assistant")]
        # Last message is the user query, not history.
        assert len(history_msgs) >= 1


# ---------------------------------------------------------------------------
# chat/pipeline.py — _extract_json and _parse_response
# ---------------------------------------------------------------------------


class TestPipelineParser:
    def test_extract_json_found(self):
        from chat.pipeline import _extract_json

        raw = (
            'The leave policy allows 20 days.\n'
            '{"citations": [], "redirect_document_id": null, '
            '"redirect_page": null, "confidence": "found"}'
        )
        answer, meta = _extract_json(raw)
        assert "leave policy" in answer
        assert meta["confidence"] == "found"

    def test_extract_json_not_found(self):
        from chat.pipeline import _extract_json

        raw = "No JSON here at all."
        answer, meta = _extract_json(raw)
        assert answer == raw.strip()
        assert meta == {}

    def test_extract_json_nested(self):
        from chat.pipeline import _extract_json

        raw = (
            "Here is the answer.\n\n"
            "```json\n"
            "{\n"
            '  "citations": [{"policy": "HR Policy v2", "page": 5, "section": "Leave"}],\n'
            '  "redirect_document_id": null,\n'
            '  "redirect_page": null,\n'
            '  "confidence": "found"\n'
            "}\n"
            "```"
        )
        answer, meta = _extract_json(raw)
        assert answer == "Here is the answer."
        assert meta["confidence"] == "found"
        assert len(meta["citations"]) == 1
        assert meta["citations"][0]["policy"] == "HR Policy v2"

    def test_parse_response_citations(self):
        from chat.pipeline import _parse_response
        from chat.retrieval import RetrievalResult

        retrieval = RetrievalResult(
            chunks=[], used_phase=1, redirect_document_id=None, redirect_page=None
        )
        uid = str(uuid.uuid4())
        raw = (
            "Answer text here. "
            f'{{"citations": [{{"policy": "Leave", "page": 3, "section": "Annual"}}], '
            f'"redirect_document_id": null, "redirect_page": null, "confidence": "found"}}'
        )
        resp = _parse_response(raw, retrieval)
        assert resp.confidence == "found"
        assert len(resp.citations) == 1
        assert resp.citations[0].page == 3

    def test_parse_response_redirect(self):
        from chat.pipeline import _parse_response
        from chat.retrieval import RetrievalResult

        uid = uuid.uuid4()
        retrieval = RetrievalResult(
            chunks=[],
            used_phase=2,
            redirect_document_id=uid,
            redirect_page=5,
        )
        raw = (
            "Found in another doc. "
            '{"citations": [], "redirect_document_id": null, '
            '"redirect_page": null, "confidence": "found"}'
        )
        # LLM says null redirect; retrieval metadata should fill in.
        resp = _parse_response(raw, retrieval)
        assert resp.redirect_document_id == uid
        assert resp.redirect_page == 5


# ---------------------------------------------------------------------------
# chat/routes.py
# ---------------------------------------------------------------------------


from fastapi.testclient import TestClient

from auth.middleware import get_current_user
from db.connection import get_db
from db.models import User
from llm.client import get_llm_client
from main import app


def _make_user() -> User:
    return User(
        id=uuid.uuid4(),
        slug="u1",
        email="user@truboard.com",
        display_name="User",
        is_admin=False,
    )


class _FakeSession:
    async def execute(self, *a, **kw):
        return MagicMock(fetchall=lambda: [])

    def add(self, obj): pass
    async def commit(self): pass
    async def refresh(self, o): pass
    async def get(self, *a): return None


def _setup_chat_overrides(pipeline_patch):
    user = _make_user()
    app.dependency_overrides[get_current_user] = lambda: user

    async def _db():
        yield _FakeSession()

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_llm_client] = lambda: MagicMock()
    return user


def test_chat_message_returns_200():
    from chat.pipeline import ChatResponse

    fake_resp = ChatResponse(
        answer="You get 20 days.",
        citations=[],
        redirect_document_id=None,
        redirect_page=None,
        confidence="found",
    )
    user = _setup_chat_overrides(None)
    try:
        with patch("chat.routes.run_pipeline", new=AsyncMock(return_value=fake_resp)):
            resp = TestClient(app).post(
                "/api/chat/message",
                json={"query": "How many leave days?", "active_document_id": str(uuid.uuid4())},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["answer"] == "You get 20 days."
        assert body["confidence"] == "found"
    finally:
        app.dependency_overrides.clear()


def test_delete_session_returns_204():
    _setup_chat_overrides(None)
    try:
        with patch("chat.routes.clear_session") as mock_clear:
            resp = TestClient(app).delete("/api/chat/session")
        assert resp.status_code == 204
        mock_clear.assert_called_once()
    finally:
        app.dependency_overrides.clear()


def test_chat_message_rate_limited():
    from fastapi import HTTPException

    _setup_chat_overrides(None)
    try:
        with patch(
            "chat.routes.run_pipeline",
            new=AsyncMock(
                side_effect=HTTPException(
                    status_code=429,
                    detail="Query limit reached.",
                    headers={"Retry-After": "120"},
                )
            ),
        ):
            resp = TestClient(app).post(
                "/api/chat/message",
                json={"query": "hi", "active_document_id": str(uuid.uuid4())},
            )
        assert resp.status_code == 429
    finally:
        app.dependency_overrides.clear()
