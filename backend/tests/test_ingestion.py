"""Tests for M4 — extractor, chunker, embedder, versioning, and new admin routes.

Uses the same fake-session / fake-blob pattern from test_documents.py.
No real DB, blob, or OpenAI calls are made.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---- extractor --------------------------------------------------------------


class TestExtractor:
    def test_bbox_overlap_detected(self):
        from admin.ingestion.extractor import _overlaps

        a = (0.0, 0.0, 100.0, 50.0)
        b = (50.0, 0.0, 150.0, 50.0)  # 50% overlap on width
        # Smaller bbox is a (area=5000); intersection = 50×50=2500 → 50% → overlap
        assert _overlaps(a, b)

    def test_bbox_no_overlap(self):
        from admin.ingestion.extractor import _overlaps

        a = (0.0, 0.0, 10.0, 10.0)
        b = (20.0, 20.0, 30.0, 30.0)  # no intersection
        assert not _overlaps(a, b)

    def test_table_to_markdown_basic(self):
        from admin.ingestion.extractor import _table_to_markdown

        rows = [["Name", "Age"], ["Alice", "30"], ["Bob", "25"]]
        md = _table_to_markdown(rows)
        assert "| Name | Age |" in md
        assert "| --- | --- |" in md
        assert "| Alice | 30 |" in md

    def test_table_to_markdown_empty(self):
        from admin.ingestion.extractor import _table_to_markdown

        assert _table_to_markdown([]) == ""

    def test_table_to_markdown_pipes_escaped(self):
        from admin.ingestion.extractor import _table_to_markdown

        rows = [["Col|A", "Col|B"]]
        md = _table_to_markdown(rows)
        assert "Col\\|A" in md

    def test_table_to_markdown_none_cells(self):
        from admin.ingestion.extractor import _table_to_markdown

        rows = [["A", None], [None, "B"]]
        md = _table_to_markdown(rows)
        assert "A" in md
        assert "B" in md


# ---- chunker ----------------------------------------------------------------


class TestChunker:
    def test_text_block_produces_chunks(self):
        from admin.ingestion.chunker import build_chunks
        from admin.ingestion.extractor import RawBlock

        long_text = "Lorem ipsum dolor sit amet. " * 200  # ~800 words
        blocks = [RawBlock(block_type="text", content=long_text, page_number=1, bbox=(0, 0, 1, 1))]
        chunks = build_chunks(blocks)
        assert len(chunks) >= 1
        for c in chunks:
            assert c.chunk_type == "text"
            assert c.page_number == 1
            assert len(c.text) > 0

    def test_table_block_is_atomic(self):
        """A table block must produce exactly one chunk regardless of size."""
        from admin.ingestion.chunker import build_chunks
        from admin.ingestion.extractor import RawBlock

        big_table = "| A | B |\n| --- | --- |\n" + "| row | data |\n" * 300
        blocks = [
            RawBlock(block_type="table", content=big_table, page_number=2, bbox=(0, 0, 1, 1))
        ]
        chunks = build_chunks(blocks)
        assert len(chunks) == 1
        assert chunks[0].chunk_type == "table"

    def test_chunk_index_is_monotone(self):
        from admin.ingestion.chunker import build_chunks
        from admin.ingestion.extractor import RawBlock

        blocks = [
            RawBlock(
                block_type="text",
                content="Word " * 100,
                page_number=i,
                bbox=(0, 0, 1, 1),
            )
            for i in range(1, 4)
        ]
        chunks = build_chunks(blocks)
        indices = [c.chunk_index for c in chunks]
        assert indices == list(range(len(chunks)))

    def test_heading_is_inherited(self):
        """Section heading should propagate to following chunks."""
        from admin.ingestion.chunker import build_chunks
        from admin.ingestion.extractor import RawBlock

        text_with_heading = "Leave Policy\n\n" + "Some policy text. " * 20
        blocks = [
            RawBlock(
                block_type="text",
                content=text_with_heading,
                page_number=1,
                bbox=(0, 0, 1, 1),
            ),
            RawBlock(
                block_type="table",
                content="| A |\n| --- |\n| 1 |",
                page_number=1,
                bbox=(0, 0, 1, 1),
            ),
        ]
        chunks = build_chunks(blocks)
        # Table chunk should inherit the heading seen in the preceding text block.
        table_chunk = next(c for c in chunks if c.chunk_type == "table")
        assert table_chunk.section_heading == "Leave Policy"

    def test_empty_blocks_produce_no_chunks(self):
        from admin.ingestion.chunker import build_chunks

        assert build_chunks([]) == []


# ---- embedder ---------------------------------------------------------------


class TestEmbedder:
    @pytest.mark.asyncio
    async def test_embed_texts_preserves_order(self):
        """embed_texts should return one embedding per input in order."""
        from admin.ingestion.embedder import embed_texts

        # Build a stub LLMClient.
        def _make_emb(i):
            m = MagicMock()
            m.embedding = [float(i)] * 1536
            return m

        response = MagicMock()
        response.data = [_make_emb(i) for i in range(3)]

        llm = MagicMock()
        llm.embedding_model = "text-embedding-3-small"
        llm.client = MagicMock()
        llm.client.embeddings = MagicMock()
        llm.client.embeddings.create = AsyncMock(return_value=response)

        texts = ["a", "b", "c"]
        result = await embed_texts(texts, llm)

        assert len(result) == 3
        for i, emb in enumerate(result):
            assert emb[0] == float(i)

    @pytest.mark.asyncio
    async def test_embed_empty_returns_empty(self):
        from admin.ingestion.embedder import embed_texts

        llm = MagicMock()
        result = await embed_texts([], llm)
        assert result == []

    @pytest.mark.asyncio
    async def test_embed_raises_on_mismatch(self):
        """RuntimeError when API returns fewer embeddings than sent."""
        from admin.ingestion.embedder import embed_texts

        response = MagicMock()
        response.data = []  # API returns 0 but we sent 2

        llm = MagicMock()
        llm.embedding_model = "text-embedding-3-small"
        llm.client = MagicMock()
        llm.client.embeddings.create = AsyncMock(return_value=response)

        with pytest.raises(RuntimeError, match="mismatch"):
            await embed_texts(["x", "y"], llm)


# ---- versioning -------------------------------------------------------------


class TestVersioning:
    @pytest.mark.asyncio
    async def test_soft_delete_sets_flags(self):
        from admin.versioning import soft_delete_policy
        from db.models import Policy

        policy = Policy(
            id=uuid.uuid4(),
            policy_name="Test",
            version=1,
            file_hash="abc",
            blob_url="https://x",
            blob_key="policies/v1/x.pdf",
            is_deleted=False,
        )

        session = MagicMock()
        session.flush = AsyncMock()
        session.execute = AsyncMock()

        await soft_delete_policy(policy, session)

        assert policy.is_deleted is True
        assert policy.deleted_at is not None
        session.execute.assert_awaited_once()  # chunks update

    @pytest.mark.asyncio
    async def test_create_replacement_increments_version(self):
        from admin.versioning import create_replacement_policy
        from db.models import Policy

        old = Policy(
            id=uuid.uuid4(),
            policy_name="HR Policy",
            version=2,
            file_hash="oldhash",
            blob_url="https://old",
            blob_key="policies/v2/old.pdf",
            is_deleted=False,
        )

        session = MagicMock()
        session.add = MagicMock()

        new_id = uuid.uuid4()
        new_policy = await create_replacement_policy(
            old_policy=old,
            new_id=new_id,
            blob_url="https://new",
            blob_key=f"policies/v3/{new_id}.pdf",
            file_hash="newhash",
            uploaded_by=uuid.uuid4(),
            session=session,
        )

        assert new_policy.version == 3
        assert new_policy.policy_name == "HR Policy"
        assert new_policy.id == new_id
        assert new_policy.is_deleted is False
        session.add.assert_called_once_with(new_policy)


# ---- admin routes (M4 endpoints) -------------------------------------------


import pytest
from fastapi.testclient import TestClient

from auth.middleware import get_current_user, require_admin
from db.connection import get_db
from db.models import Policy, User
from main import app
from storage.blob import get_blob_service


def _make_user(*, is_admin: bool = True) -> User:
    return User(
        id=uuid.uuid4(),
        slug=f"test-{uuid.uuid4()}",
        email="admin@truboard.com",
        display_name="Admin",
        is_admin=is_admin,
    )


def _make_policy(name: str = "Travel Policy", version: int = 1) -> Policy:
    return Policy(
        id=uuid.uuid4(),
        policy_name=name,
        version=version,
        file_hash="deadbeef",
        blob_url="https://acct.blob.core.windows.net/c/policies/v1/x.pdf",
        blob_key="policies/v1/x.pdf",
        is_deleted=False,
    )


class _FakeResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None


class _FakeSession:
    def __init__(self, items=None):
        self._items = items or []
        self.added = []

    async def execute(self, *_args, **_kwargs):
        return _FakeResult(self.added + self._items)

    def add(self, obj):
        self.added.append(obj)

    def add_all(self, objs):
        self.added.extend(objs)

    async def commit(self):
        pass

    async def refresh(self, _obj):
        pass

    async def get(self, model, pk):
        for item in self._items + self.added:
            if hasattr(item, "id") and item.id == pk:
                return item
        return None

    async def flush(self):
        pass


class _StubBlob:
    async def upload_pdf(self, content: bytes, blob_key: str) -> str:
        return f"https://acct.blob.core.windows.net/c/{blob_key}"

    def generate_sas_url(self, blob_key: str):
        return (f"https://acct.blob.core.windows.net/c/{blob_key}?sig=stub", datetime.now(UTC))


def _setup(items=None):
    user = _make_user()
    session = _FakeSession(items)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[require_admin] = lambda: user

    async def _db_gen():
        yield session

    app.dependency_overrides[get_db] = _db_gen
    app.dependency_overrides[get_blob_service] = lambda: _StubBlob()
    return session


def test_list_all_policies_includes_deleted():
    active = _make_policy("Alpha")
    deleted = _make_policy("Beta")
    deleted.is_deleted = True
    _setup([active, deleted])
    try:
        resp = TestClient(app).get("/api/admin/policies")
        assert resp.status_code == 200
        names = [p["policy_name"] for p in resp.json()]
        assert "Alpha" in names
        assert "Beta" in names
    finally:
        app.dependency_overrides.clear()


def test_upload_and_ingest_returns_job_id():
    _setup([])
    try:
        with patch("admin.routes.register_job"), patch("admin.routes.run_ingestion_job"):
            resp = TestClient(app).post(
                "/api/admin/upload-and-ingest",
                files=[("file", ("policy.pdf", b"%PDF-1.7 content", "application/pdf"))],
            )
        assert resp.status_code == 200
        body = resp.json()
        assert "job_id" in body
        assert body["status"] == "queued"
    finally:
        app.dependency_overrides.clear()


def test_upload_and_ingest_rejects_non_pdf():
    _setup([])
    try:
        resp = TestClient(app).post(
            "/api/admin/upload-and-ingest",
            files=[("file", ("notes.txt", b"hello", "text/plain"))],
        )
        assert resp.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_replace_policy_not_found():
    _setup([])  # empty — no existing policy
    try:
        resp = TestClient(app).post(
            f"/api/admin/policies/{uuid.uuid4()}/replace",
            files=[("file", ("new.pdf", b"%PDF-1.7 new", "application/pdf"))],
        )
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()
