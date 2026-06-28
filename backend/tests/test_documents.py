"""Tests for M3 — storage SAS generation, documents API, and admin upload.

Uses dependency overrides + a fake async session, so no real DB or Azure call is made.
"""

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from admin.routes import upload_documents  # noqa: F401 — ensures router imports cleanly
from auth.middleware import get_current_user, require_admin
from config import get_settings
from db.connection import get_db
from db.models import Policy, User
from main import app
from storage.blob import BlobStorageService, get_blob_service

# ---- fakes -------------------------------------------------------------------


class _FakeResult:
    def __init__(self, items: list):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None


class _FakeSession:
    """Minimal AsyncSession stand-in. execute() ignores the WHERE clause and returns
    rows added this session plus the seeded rows — enough to model the dedup query
    seeing a just-committed row within the same batch."""

    def __init__(self, items: list | None = None):
        self._items = items or []
        self.added: list = []

    async def execute(self, *_args, **_kwargs):
        return _FakeResult(self.added + self._items)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        pass

    async def refresh(self, _obj):
        pass


class _StubBlob:
    async def upload_pdf(self, content: bytes, blob_key: str) -> str:
        return f"https://acct.blob.core.windows.net/c/{blob_key}"

    def generate_sas_url(self, blob_key: str) -> tuple[str, datetime]:
        return (f"https://acct.blob.core.windows.net/c/{blob_key}?sig=stub", datetime.now(UTC))


def _make_user(*, is_admin: bool = False) -> User:
    return User(
        id=uuid.uuid4(),
        slug=f"test-{uuid.uuid4()}",
        email="test@truboard.com",
        display_name="Test User",
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


def _override(session_items=None, *, admin=False, blob=None):
    user = _make_user(is_admin=admin)
    session = _FakeSession(session_items)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[require_admin] = lambda: user
    app.dependency_overrides[get_db] = lambda: session

    async def _db_gen():
        yield session

    app.dependency_overrides[get_db] = _db_gen
    app.dependency_overrides[get_blob_service] = lambda: blob or _StubBlob()
    return session


# ---- storage: pure SAS generation -------------------------------------------


def test_generate_sas_url_format_and_expiry():
    service = BlobStorageService(get_settings())  # dummy creds from conftest; no network
    before = datetime.now(UTC)
    url, expires_at = service.generate_sas_url("policies/v1/abc.pdf")

    assert url.startswith("https://teststorage.blob.core.windows.net/")
    assert "policies/v1/abc.pdf?" in url
    assert "sig=" in url  # signature present
    delta_hours = (expires_at - before).total_seconds() / 3600
    assert 0.99 <= delta_hours <= 1.01  # SAS_TOKEN_EXPIRY_HOURS default = 1


# ---- GET /api/documents ------------------------------------------------------


def test_list_documents():
    _override([_make_policy("Alpha"), _make_policy("Beta")])
    try:
        resp = TestClient(app).get("/api/documents")
        assert resp.status_code == 200
        body = resp.json()
        assert [d["policy_name"] for d in body] == ["Alpha", "Beta"]
        assert all({"id", "policy_name", "version"} == set(d) for d in body)
    finally:
        app.dependency_overrides.clear()


# ---- GET /api/documents/{id}/url --------------------------------------------


def test_get_document_url_found():
    policy = _make_policy()
    _override([policy])
    try:
        resp = TestClient(app).get(f"/api/documents/{policy.id}/url")
        assert resp.status_code == 200
        body = resp.json()
        assert policy.blob_key in body["url"]
        assert "expires_at" in body
    finally:
        app.dependency_overrides.clear()


def test_get_document_url_not_found():
    _override([])  # empty → scalar_one_or_none returns None
    try:
        resp = TestClient(app).get(f"/api/documents/{uuid.uuid4()}/url")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()


# ---- POST /api/admin/upload --------------------------------------------------


def test_upload_rejects_non_pdf():
    # Per-file results: a bad file is reported as an error item, not an HTTP error.
    _override([], admin=True)
    try:
        resp = TestClient(app).post(
            "/api/admin/upload",
            files=[("files", ("notes.txt", b"hello world", "text/plain"))],
        )
        assert resp.status_code == 200
        item = resp.json()[0]
        assert item["status"] == "error"
        assert "PDF" in item["error"]
    finally:
        app.dependency_overrides.clear()


def test_upload_rejects_duplicate_hash():
    _override([_make_policy()], admin=True)  # existing row → dedup hit
    try:
        resp = TestClient(app).post(
            "/api/admin/upload",
            files=[("files", ("doc.pdf", b"%PDF-1.7 fake", "application/pdf"))],
        )
        assert resp.status_code == 200
        item = resp.json()[0]
        assert item["status"] == "error"
        assert "already" in item["error"].lower()
    finally:
        app.dependency_overrides.clear()


def test_upload_success():
    session = _override([], admin=True)  # no existing row → proceeds
    try:
        resp = TestClient(app).post(
            "/api/admin/upload",
            files=[("files", ("Leave Policy.pdf", b"%PDF-1.7 content", "application/pdf"))],
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["status"] == "uploaded"
        assert body[0]["policy_name"] == "Leave Policy"  # derived from filename stem
        assert body[0]["version"] == 1
        assert len(session.added) == 1
        assert session.added[0].blob_key.startswith("policies/v1/")
    finally:
        app.dependency_overrides.clear()


def test_upload_multiple_mixed():
    # Two files; the second duplicates the first's hash (same bytes) → first
    # uploads, second is reported as an error. Dedup catches it because each row
    # commits before the next file is processed.
    session = _override([], admin=True)
    try:
        pdf = b"%PDF-1.7 same-bytes"
        resp = TestClient(app).post(
            "/api/admin/upload",
            files=[
                ("files", ("a.pdf", pdf, "application/pdf")),
                ("files", ("b.pdf", pdf, "application/pdf")),
            ],
        )
        assert resp.status_code == 200
        body = resp.json()
        assert [i["status"] for i in body] == ["uploaded", "error"]
        assert body[0]["policy_name"] == "a"
        assert len(session.added) == 1  # only the first persisted
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("size_mb", [51])
def test_upload_rejects_oversize(size_mb):
    _override([], admin=True)
    try:
        big = b"%PDF" + b"0" * (size_mb * 1024 * 1024)
        resp = TestClient(app).post(
            "/api/admin/upload",
            files=[("files", ("big.pdf", big, "application/pdf"))],
        )
        assert resp.status_code == 200
        item = resp.json()[0]
        assert item["status"] == "error"
        assert "limit" in item["error"].lower()
    finally:
        app.dependency_overrides.clear()
